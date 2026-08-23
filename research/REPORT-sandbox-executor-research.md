# Hermetic Sandbox-Executor + дистиллированный фидбек для LLM-агентов: исследование реализуемости и новизны

**Дата:** 2026-08-22 · **Автор:** RarProd1000 (исследование собрано с помощью Claude; 6 параллельных обзоров, ~780 источников просмотрено, ~350 процитировано). Сырые отчёты с URL и датами: `research/raw/01…06`.

---

## 0. Вердикт в пяти пунктах

1. **Проблема реальна и измерена.** Вывод инструментов (stdout/stderr, логи тестов, файлы) — это 45–84 % токенов в траекториях код-агентов: 84 % на ход в SWE-agent (JetBrains, NeurIPS'25 DL4Code), 45.7 % на SWE-bench Verified и **67.8 % на Terminal-Bench** (CoACT, июль 2026), «>70 %» (SWE-Pruner Pro). Один вызов инструмента может стоить 580 k (Claude Code `getDiagnostics`) или 948 k токенов (Codex `rg`). Задача в Claude Code стоит в среднем $8.17 и 21.6 M токенов (Artificial Analysis, 2026). Anthropic сам рекомендует фильтровать вывод тестов хуками «с десятков тысяч токенов до сотен».

2. **Наивное решение — «сжать stdout регэкспом» — уже сделано 15+ раз и не работает как обещано.** RTK (Rust Token Killer, январь 2026) — **77 k звёзд**, и два независимых исследования показали: JetBrains (июль 2026, 425 прогонов) — **+7.6 % к стоимости** и +13.8 % ходов; arXiv 2607.12161 «Token Reduction Is Not Cost Reduction» (2 908 прогонов) — корреляция «сокращение токенов ↔ стоимость» **r = 0.15**, RTK-ML −38 % токенов, но **+6.8 % стоимости**. Причины: prompt-cache экономика (90–97 % токенов — кэш-чтения по 10 % цены) и поведенческий сдвиг (агент делает больше ходов, чтобы доразобраться). **Если делать ещё один RTK — это провал на ревью.**

3. **Что реально никто не сделал** (проверено по ~100 инструментам, 15 харнессам, ~60 статьям): (а) **типизированный контракт фидбека**, который выдаёт сам экзекьютор — распарсенные диагностики компилятора, объекты ASan/UBSan/crash с символизированным бэктрейсом, root-cause-группировка падений тестов — вместо байтов; (б) **дельты на уровне диагностик** между прогонами («2 ошибки исправлены, 1 новая, 3 без изменений; crash переехал из X в Y») — ни один инструмент и ни одна статья; (в) **детерминизм как предпосылка для дельт** (без герметичности дельты отравляются ASLR-адресами, временем, порядком потоков) — никто так не ставил вопрос; (г) оценка на C/C++/Rust с санитайзерами с учётом **billed cost + turns**, а не только токенов. Все песочницы (E2B, Modal, Daytona, Vercel, Docker Sandboxes, K8s agent-sandbox, OpenSandbox, OpenShell…) возвращают сырой stdout; все харнессы режут по байтам (Codex 10 KiB, Claude Code 30 k chars, Gemini 40 k, Terminus 10 KB); только Gemini CLI суммаризирует LLM-ом.

4. **Наука поддерживает гипотезу, но требует правильной метрики.** Форма фидбека при фиксированной модели даёт от ±3–8 pp (SWE-agent ACI) до +42–44 pp (VeriHarness, структурированные поля) и 10.7 → 73.7 % (RustAssistant, формат промпта); почти весь выигрыш в первых 3–4 итерациях; длиннее ≠ лучше (Fact Selection −8.2 % при «всех фактах», LOCA-bench 96 → 14.7 % при росте контекста 8 k → 256 k). Открытые вопросы, которые может закрыть твоя статья: нет контролируемого сравнения raw vs distilled sanitizer-вывода по success **и** cost; нет dose-response по длине фидбека для компилятора/краша; delta-feedback не изучен; влияние недетерминированных артефактов краша на агентов не измерено.

5. **Решение: делать, но с правильной рамкой.** Не «песочница + сжатие», а **«Feedback as a typed API + deltas need determinism»**. Главная метрика — **число ходов до решения и billed cost** (с учётом кэша), не байты. Бейзлайны — observation masking (−50 % бесплатно) и RTK. Задачи — C/C++/Rust с ASan (SEC-bench / ARVO / ComBench / CRUST-Bench + Terminal-Bench-подмножество), где сырой вывод огромен и эффект виден. Формат — workshop-paper (DL4Code @ ICML, ICLR/NeurIPS agents, EuroSys/SOSP workshop) + arXiv + открытый Rust-инструмент. Реалистично соло за 2.5–3 месяца при условии, что Rust-ядро ты пишешь уверенно (Andromeda это подтверждает).

**Главный риск** — эффект окажется малым или его съест кэш-экономика. Митигация: мерить turns/cost/cache-reads, N ≥ 5 прогонов (шум одиночного прогона 2–6 pp даже при temperature 0), и выбирать задачи, где сырой вывод огромен.

---

## 1. Что происходит в мире (январь–август 2026)

**Рынок песочниц для агентов взорвался, но никто не трогает вывод.**
- Modal: Series C $355 M при оценке $4.65 B (май 2026), >$300 M ARR, песочницы — >⅓ выручки. Daytona: $24 M A (фев) + $48 M по SEC (авг). E2B: 1 B+ песочниц. Vercel платит **$1 M за побег из Firecracker-песочницы** (18 авг – 1 сен 2026). Docker Sandboxes (microVM на агента, янв), K8s SIG `agent-sandbox` v0.5.6 (20 авг), Alibaba OpenSandbox (14.5 k★), NVIDIA OpenShell (8.3 k★), GKE Agent Sandbox, Red Hat build. OpenAI Agents SDK и Claude Managed Agents получили нативные интеграции с E2B/Modal/Daytona/Vercel/Cloudflare.
- Anthropic опубликовал «How we contain Claude» (25 мая 2026): claude.ai = gVisor, Claude Code = Seatbelt/bwrap, Cowork = полная VM; принцип «containment at the environment layer first».
- **Terminal-Bench 2.1** (22 авг 2026): Claude Code + Fable 5 83.8 %, Codex + GPT-5.5 83.1 %, Terminus 2 80.4 %, mini-SWE-agent 76.2 %. Версия 2.1 починила 28/89 задач: 9 — дрейф внешних зависимостей, 8 — несоответствие ресурсов, 11 — мисспецификации; **`polyglot-rust-c` +74 pp, `polyglot-c-py` +84 pp после починки** — низкоуровневые компиляционные задачи оказались самыми чувствительными к среде.
- **Anthropic «Quantifying infrastructure noise» (5 фев 2026):** разброс 6 pp между конфигурациями контейнеров на TB 2.0 (p < 0.01); «различия ниже 3 pp заслуживают скепсиса, пока конфигурация среды не задокументирована и не совпадает». Это прямой аргумент за герметичный исполнитель.
- Безопасность: Claude Code CVE-2026-25725 (инъекция хуков через `.claude/settings.json`), CVE-2026-39861 (symlink-запись), SOCKS5-обход; Cursor «DuneSlide» CVSS 9.8; runc CVE-2025-31133/52565/52881; «Copy Fail» CVE-2026-31431 (ядро, mitigation — блок AF_ALG через seccomp); 13 CVE в vm2; SandboxEscapeBench: Opus 4.5 сбегает в 49 % сценариев по ~$1 за попытку — «plain Docker недостаточен по умолчанию».

**Как харнессы режут вывод сегодня** (по исходникам):

| Харнесс | Стратегия |
|---|---|
| Claude Code | Bash ≤ 30 000 chars, middle-truncate; больше → файл + превью ~2 KB; `PostToolUse` хук может подменить результат (`updatedToolOutput`) |
| Codex CLI | 256 строк или 10 KiB, head 128 + tail 128 (`truncate.rs`) |
| Gemini CLI | 40 000 chars, 20 %/80 %; **единственный с LLM-суммаризацией** (пороги 10 k/20 k токенов) |
| OpenHands | 30 000 chars middle; предложение offload-в-файл закрыто «not planned» |
| Terminus 2 (TB reference) | 10 000 байт first/last half |
| mini-SWE-agent | > 10 000 chars → 5 000 + 5 000 |
| Roo Code / Cursor | 500 строк / ~20 k; Cursor staff: «длинный вывод путает агентов» |
| E2B / Modal / Daytona / Vercel / Docker Sandboxes / K8s | сырой stdout, без ограничений |

**Ни один** не парсит диагностики компилятора, санитайзеры, бэктрейсы; ни один не считает дельты; нет схемы результата ни в одном стандарте (OpenSandbox Protocol, K8s CRD, провайдерские API стандартизируют lifecycle/exec, а не форму результата).

---

## 2. Токен-экономика: числа, на которые можно опираться

| Что | Число | Источник |
|---|---|---|
| Доля observation-токенов | 84 %/ход (SWE-agent); 45.7 % SWE-bench V; 67.8 % Terminal-Bench; >70 % | Complexity Trap 2508.21433; CoACT 2607.02911; SWE-Pruner Pro 2607.18213 |
| Стоимость задачи | Claude Code $8.17 / 21.6 M tok; Codex $6.42 / 13.2 M; LH-Terminal-Bench $10.21 / 9.66 M | Artificial Analysis 2026; arXiv 2607.08964 |
| Доля кэш-чтений | 90–97 % токенов (Claude Code 97 % cache hit) | Claude Code docs; Artificial Analysis |
| Разброс затрат на одну задачу между прогонами | до 30× | «How Do AI Agents Spend Your Money?» 2604.22750 |
| Маскирование старых observations | −50…57 % стоимости, success ≥ LLM-суммаризации; суммаризация удлиняет траектории на 13–15 % | Complexity Trap |
| AgentDiet (FSE'26) / ACON (ICML'26) / SWE-Pruner / CoACT | −40…60 % / −26…54 % / −23…54 % / −33 % токенов при +0…+4 pp | см. raw/02 |
| Отрицательные результаты | минификация кода −42 % токенов, но **−12 pp** success; LLMLingua-2 −7 pp; CoACT −1.5 pp на DeepSeek | TU Wien 2606.01326; CoACT |
| Деградация от длины | LOCA-bench Opus 4.5: 96 % → 14.7 % (8 k → 256 k); tool-noise ≈ −20 pp (AgentNoiseBench) | 2602.07962; 2602.11348 |
| Anthropic | code-execution-with-MCP 150 k → 2 k (98.7 %); context editing −84 % за 100 ходов; PTC −37 %; $13/dev/день | engineering blog 2025; docs 2026 |
| **RTK независимо** | +7.6 % cost (p = 0.004), +13.8 % turns; r(tokens, cost) = 0.15; RTK-ML +6.8 % cost при −38 % tokens; Headroom +48 % | JetBrains Jul 2026; arXiv 2607.12161 |

**Вывод для статьи:** метрика «токены» дискредитирована. Надо отчитывать **billed cost (с кэшем), turns-to-solve, success, wall-clock, cache-hit**, плюс **токены по типу вывода** (логи тестов vs файлы vs grep vs билд) — такой разбивки в литературе нет вообще.

---

## 3. Что наука знает о форме фидбека

**Установлено:**
- Execution-feedback бьёт его отсутствие с большим отрывом (Self-Debugging +12; Reflexion 80 → 91; CRUST-Bench 15 → 37; Bosch C→Rust +24 pp, различия моделей исчезают при включённом фидбеке).
- Почти весь выигрыш — в первых 2–4 итерациях («Is Three the Magic Number?», FeedbackEval, CRUST-Bench); форма кривой определяется дизайном фидбека сильнее, чем моделью.
- Форма фидбека при фиксированной модели: SWE-agent ACI ±3–8 pp; RustAssistant 10.7 → 73.7 % от формата промпта, отключение группировки ошибок роняет до 14 %; VeriHarness {location, observed, admissible} +42–44 pp (JSON vs проза — н.з.); PGS минимальный контрпример +13.2 pp при меньшем числе токенов; Generative Compilation: 13.8 → 5.5 диагностик на отчёт → меньше ошибок компиляции.
- Больше ≠ лучше: Fact Selection (все факты −8.2 % pass@1), SWE-agent (полный файл −5.3, полная история −3.0), длина баг-репорта OR 0.49 на SD, «Mixed < Expert» на SWE-bench; суммаризация прячет сигналы остановки. Но Type-Error Ablation (2026): *релевантная* структурированная детализация помогает (201 → 317/600). Драйвер — релевантность и структура, не длина.
- Для memory-safety багов: отчёт санитайзера достаточен для пространственных багов (stack-BOF), темпоральные (UAF) требуют динамического состояния (DebugHarness: 89.5 % на SEC-bench при $0.09/уязвимость; GDB-only 82 %, sanitizer+static 77 %); «plausible» патчи по крашу сильно переоценивают корректность (AutoPatchBench 60 % → 5–11 %).
- Шум оценки: одиночный прогон ±2.2–6.0 pp, SD > 1.5 pp даже при T = 0; ~9 прогонов, чтобы увидеть эффект 2 pp (arXiv 2602.07150).

**Открыто (= место для твоей статьи):**
1. Нет контролируемого исследования raw vs distilled/structured sanitizer-вывода (ASan/UBSan/MSan/TSan) по success **и** cost; WilliamT (regex-дистилляция ASan → 358 багов за $0.68, −45.9 % токенов в связке) и DebugHarness никогда не сравнивали с полным отчётом.
2. Нет dose-response по длине/вербозности фидбека компилятора/краша в агентных циклах.
3. **Delta-feedback** («что изменилось с прошлого прогона») и сжатие build/test-логов для C/C++/Rust не изучены; Squeez меряет только recall.
4. Не измерено, как недетерминированные артефакты (адреса ASLR, interleaving потоков, флаки-репродукция) сбивают агентов.
5. C/C++/Rust на Multi-SWE-bench < 16 % без анализа влияния фидбека; UBSan/MSan/Valgrind-фидбек практически не изучен.

---

## 4. Новизна: матрица

| Компонент | RTK / token-saver / squeez | Claude Code / Codex / Gemini / Terminus 2 | Complexity Trap / AgentDiet / CoACT / TACO | DebugHarness / CodeRover-S | Песочницы (nono, hakoniwa, Codex bwrap, AgentCgroup) |
|---|---|---|---|---|---|
| Герметичная Rust-песочница | ○ | ◐ | ○ | ○ | ● (но без герметичного профиля) |
| Детерминированный профиль | ○ | ○ | ○ | ○ | ◐ |
| Парсинг диагностик компилятора | ◐ | ◐ (LSP) | ○ | ○ | ○ |
| Дистилляция санитайзера/бэктрейса | ○ | ○ | ○ | ◐ (LLM-ом) | ○ |
| Root-cause падений тестов | ◐ | ○ | ○ | ○ | ○ |
| **Дельта vs прошлый прогон** | ◐ (dedup) | ○ | ◐ (LLM «expired») | ○ | ○ |
| Tokens + turns + billed cost на бенче | ○ (опровергнуто) | ○ | ● | ◐ | ○ |

**Новое:** типизированный контракт от экзекьютора; дельты на уровне диагностик; детерминизм как предпосылка дельт; C/C++/Rust + санитайзеры с cost/turns. **Инженерная интеграция, не новизна:** сама Rust-песочница (hakoniwa, nono, Sandlock, youki), regex-фильтры pytest/cargo (RTK + 15 клонов), LLM-суммаризация логов (Gemini CLI, DebugHarness), masking, хуки.

**Что скажет скептик-ревьюер и чем отвечать:**
- «RTK 77 k★ и не экономит — чем ты отличаешься?» → меряем billed cost, turns, cache; показываем, что дельты сокращают *ходы*, а не байты.
- «Masking даёт 50 % бесплатно» → masking — бейзлайн, мы поверх него.
- «Claude Code уже кладёт в файл, модель может grep-нуть» → это и есть дополнительные ходы; измеряем.
- «Дельты теряют информацию» → показываем failure cases и режим «раскрыть полный отчёт по запросу» (reversible, как squeez через MCP).
- «Детерминизм — определи» → профиль (syscalls, clock, ASLR, seed, scheduling) + измеренное снижение флаки.
- «Это TACO-правила руками?» → TACO учит правила из траекторий; у нас — парсеры по спецификации формата (SARIF/`cargo --message-format=json`/ASan grammar) + дельты + детерминизм.

---

## 5. Детерминизм и системная часть

**Почему это не декорация:** Anthropic показал 6 pp шума от конфигурации контейнера; TB 2.1 — компиляционные задачи чувствительнее всего к среде; «Grounded Scaling» (arXiv 2606.22495, июнь 2026): успех k-шаговой задачи деградирует как δ^k с недетерминизмом среды; COBALT: модели учатся «следовать фидбеку, не рассуждая о его валидности» — флаки-фидбек особенно вреден. **Для дельт детерминизм обязателен:** если адреса в бэктрейсе меняются от ASLR, а порядок тестов — от потоков, дельта «что нового» становится мусором.

**Что есть в мире:** Hermit (Meta, Rust, ptrace, 3–6× slowdown, maintenance mode — но в 2026 в репо добавили `AGENTS.md`/`.claude/skills`); rr; Antithesis (коммерческий детерминированный гипервизор, $105 M; в 2026 выпустили «skills для агентов»); Bazel `linux-sandbox.cc` (clone с NEWUSER|NEWNS|NEWIPC|NEWPID, без seccomp); Nix; reproducible-builds.org (SOURCE_DATE_EPOCH, `-ffile-prefix-map`); DeltaBox (checkpoint 14.6 мс, restore 5–8 мс, overlayfs + reflink); Crab (ZFS-снапшоты ≤ 22 мс, rollback экономит 36 % токенов); **Sandlock** (Rust ~7 k LOC, Landlock+seccomp-notify, 5 мс старт, 44× быстрее Docker, но лимиты кооперативные). **Ни одна коммерческая песочница не заявляет детерминизм.**

**Рекомендуемый стек (Rust, Linux/WSL2):**
1. `clone3` с NEWUSER|NEWNS|NEWPID|NEWNET|NEWIPC|NEWUTS|NEWCGROUP|**NEWTIME** (rustix/nix) — как Bazel/Nix/youki; NEWTIME даёт смещаемые CLOCK_MONOTONIC/BOOTTIME (libfaketime хрупок).
2. Rootfs: read-only контент-адресуемая база + overlayfs/tmpfs; `pivot_root` → `umount2(MNT_DETACH)`; маскировать `/proc/{kcore,sysrq-trigger}`; свежие `/proc`, `/dev`; все bind — через `openat2(RESOLVE_NO_SYMLINKS|RESOLVE_BENEATH)` (урок runc-2025).
3. cgroup v2 leaf (`cgroups-rs`): `memory.max`, `pids.max`, `cpu.max`; floor = ceiling с калиброванным запасом, **записывать конфиг в каждый прогон** (Anthropic infra-noise).
4. `PR_SET_NO_NEW_PRIVS`, сброс capabilities (`caps`), rlimits.
5. `seccompiler` allowlist: deny `io_uring_*`, `ptrace`, `keyctl`, `bpf`, `perf_event_open`, `userfaultfd`, `unshare/setns/mount` после настройки; **блок AF_ALG** (Copy Fail).
6. Landlock поверх (ABI-детект; WSL2 ядро 6.6 = ABI V4).
7. Egress: NEWNET без veth; при необходимости unix-socket → host-proxy с allowlist (дизайн Anthropic srt), никогда Docker socket.
8. Snapshot/fork: overlayfs-upper diff + CRIU/template-fork (5–15 мс по DeltaBox) — для tree-search и повторов; reseed RNG, reset clock на каждый fork.
9. Путь эскалации: тот же формат задачи под Firecracker (Harbor-style backend swap); Hermit — только для воспроизведения флаки, не для безопасности.

**Герметичный профиль (чеклист):** NEWNET без маршрута; vendored-зависимости; NEWTIME + `SOURCE_DATE_EPOCH`, `TZ=UTC`; фиксированные hostname/uid/umask/`HOME`/`PATH`/`LC_ALL=C.UTF-8`/`PYTHONHASHSEED=0`/`CARGO_HOME`; `personality(ADDR_NO_RANDOMIZE)` для воспроизводимых адресов в бэктрейсе; seeded `getrandom` через seccomp-notify; CPU-pinning, фиксированный `nproc`, single-core режим для replay; N ≥ 3 повтора для детекта флаки; телеметрия stdout/stderr/exit/syscall-denials/tokens/cost на прогон.

**Твоя машина (проверено 22 авг):** WSL2 Ubuntu, ядро 6.6.114, cgroup v2 (cpuset cpu io memory pids), user namespaces (max 31 565), seccomp, bwrap, gcc 15.2, clang 21.1, Python 3.14, 12 ядер. Нет Rust-тулчейна и gdb в WSL — ставится за минуты. Landlock — только ABI V4 (без IOCTL_DEV/scopes). Firecracker в WSL2 — «с бубном», не планировать.

---

## 6. Робототехнический угол (если нужен для портфолио)

**Состояние:** Eureka/DrEureka/Text2Reward/L2R (reward-код + скалярная «reflection»; удаление reflection −28.6 %), Code-as-Policies, RoboEval (символический сим + temporal-logic оракул). 2026: **CaP-X** (sandbox + Visual Differencing + 187 задач, GPU), **RHO «Your Coding Agent is Secretly a Roboticist»** (Berkeley, июнь 2026 — sidecar-контейнер, whitelisted «REaaS», структурированная side-info, **625 M input tokens, $2 821** за 70 % на CaP-Bench — ближайшая работа), RATs (verdict: категория отказа + первый упавший шаг + подсказка), ASPIRE (NVIDIA; multimodal traces с контактной динамикой), RDA (скалярная reflection прячет разные failure modes), FAEA (Claude Agent SDK без изменений: 85–96 % с privileged state).

**Gap:** ни одна robotics-работа не сравнивает представления фидбека по tokens-per-success; только RHO документирует реальную изоляцию; никто не оценивает namespace/seccomp-изоляцию LLM-кода робота как вклад; почти всё — GPU + $1 k+ бюджеты. **Не сделано:** CPU-only детерминированный MuJoCo (12 327 шагов/с humanoid single-thread; «simulations are deterministic» при pinned binary + seed + 1 поток/env) в namespace-песочнице + **типизированный «physical verdict»** (success, нарушения лимитов с временем первого нарушения, насыщение моментов, контакты, запас устойчивости) vs сырые трейсы/VLM-капшены + измерение tokens/turns.

**Три семейства задач для эксперимента:** (1) низкоуровневый синтез контроллера — MuJoCo/Gymnasium (InvertedDoublePendulum, Hopper, Reacher, Menagerie-руки), агент пишет PD/LQR/MPC, вердикт: return, settle time, нарушения + timestamp, NaN/fall, 10-seed eval; (2) манипуляция из примитивов — Robosuite Lift/Stack или ManiSkill3 PickCube (CPU), сравнение stdout-only / structured verdict / VDM; (3) Eureka-lite — reward для sampling-MPC или 5-мин PPO, reflection сжата до квантилей + теги failure taxonomy.

**Рекомендация:** robotics — **фаза 2** после основной статьи; тот же экзекьютор и тот же контракт вердикта, только плагин «физический вердикт». Это превращает два infra-проекта в robotics-портфолио без переписывания ядра.

---

## 7. Дизайн эксперимента для статьи

**Гипотезы.**
- H1 (форма): структурированный фидбек (диагностики + crash-объект + root-cause тестов) при равной информации снижает turns-to-solve и billed cost vs raw/head-tail при не худшем success.
- H2 (дельты): delta-feedback между прогонами дополнительно снижает turns на многоитерационных задачах и не ухудшает success; эффект пропадает без герметичного профиля (дельты зашумлены).
- H3 (детерминизм): герметичный профиль снижает дисперсию исхода между прогонами (pass@1 SD) и долю «инфраструктурных» ошибок.

**Условия (6):** (A) raw; (B) head/tail-truncation как Claude Code/Codex (30 k / 10 KiB); (C) RTK-style regex-сжатие; (D) observation masking M = 10; (E) **structured** (наш контракт); (F) **structured + delta**. Плюс (G) structured без герметичного профиля — для H2/H3.

**Задачи (где сырой вывод большой):** SEC-bench/ARVO подмножество (C/C++ + ASan/UBSan, воспроизводимые PoC; DebugHarness как SOTA-референс), ComBench (200 repo-level компиляционных ошибок C/C++), CRUST-Bench (rustc-циклы), Terminal-Bench 2.1 compile-подмножество (`polyglot-*`), + 30–50 собственных задач с memory-багами и большими тест-сьютами. Итого 150–250 задач; для пилота — 60.

**Модели:** Claude Sonnet/Opus (API), один открытый (Qwen3-Coder) для воспроизводимости. **Харнессы:** mini-SWE-agent (открытый, #8 TB 2.1, легко патчить) и Claude Code через `PostToolUse` хук `updatedToolOutput` (фронтир-харнесс — закрывает претензию ревьюера).

**Метрики:** success (pass@1, N ≥ 5 прогонов, CI), turns-to-solve, **billed cost с кэшем**, tokens по типу (tool output / files / reasoning), cache-hit, wall-clock, step-limit/timeout rate, дисперсия между прогонами; разбивка по классу бага (spatial vs temporal).

**Threats to validity / что честно указать:** кэш-экономика (клиринг результатов инвалидирует префикс); зависимость от модели (CoACT −1.5 pp на одной из моделей); Python-bias литературы; шум 2–6 pp; «plausible ≠ correct» для crash-патчей (дифференциальные тесты там, где есть).

**Ожидаемый формат:** 8–10 страниц workshop (DL4Code @ ICML 2026 — там вышла Complexity Trap, магистерская; ICLR/NeurIPS agent workshops; EuroSys/SOSP workshop для systems-рамки) + arXiv + репо. Для HN-трекшна — рамка №3: «Token reduction ≠ cost reduction — what actually does?».

---

## 8. Архитектура и план (Rust)

```
sandbox-executor/
├── crates/
│   ├── hermit-core/      # clone3/ns/pivot_root/cgroups v2/seccomp/landlock/NEWTIME; hermetic profile
│   ├── feedback/         # парсеры: gcc/clang SARIF+json, cargo --message-format=json, ASan/UBSan grammar,
│   │                     #   gdb -batch backtrace → frames, pytest/ctest/cargo test → root-cause groups;
│   │                     #   Verdict schema; Delta(prev, cur)
│   ├── agent-loop/       # Claude API / OpenAI-compatible; бюджет итераций; телеметрия tokens/cost/cache
│   ├── harness-adapters/ # Claude Code PostToolUse hook; mini-SWE-agent; Harbor backend
│   └── cli/              # `sbx run|verdict|diff|bench|selftest`
├── bench/                # задачи, раннер, N-прогонов, отчёты (JSON) + графики
└── docs/                 # verdict schema, hermetic profile, threat model
```

**Из Light-Andromeda переезжает:** workspace-структура, CI (fmt/clippy `-D warnings`/test), Dockerfile, FFI-паттерн (`csrc/*.c` + `build.rs`) на случай libxdp-подобных либ, zero-copy парсеры как views над `&[u8]` (для стримингового парсинга логов), policy/mechanism split (`raw → Verdict` чистая функция, `apply` отдельно), культура бенчей с JSON-выводом.

**План (~10 недель):**
- Нед. 1–2 — `hermit-core`: изоляция, лимиты, hermetic profile, тесты на побег (сеть, fork-bomb, /proc, запись вне overlay, AF_ALG), бенч старта (vs bwrap vs docker).
- Нед. 3–4 — `feedback`: парсеры + Verdict-схема + Delta; фикстуры из реальных ASan/rustc/pytest логов; property-тесты.
- Нед. 5–6 — `agent-loop` + адаптеры (mini-SWE-agent, Claude Code hook); пилот на 60 задачах × 6 условий × 3 прогона.
- Нед. 7–8 — полный eval (N ≥ 5), анализ, графики cost/turns/success, failure cases дельт.
- Нед. 9–10 — статья + README с таблицами + релиз crate/бинаря; опц. MuJoCo-плагин вердикта.

**Что выкладывать как продукт:** `sbx` — бинарь + Claude Code plugin (hook), который (1) запускает команду герметично, (2) возвращает Verdict+Delta вместо сырого вывода, (3) по запросу раскрывает полный лог. Это напрямую «для всех, кто сидит в Claude Code».

---

## 9. Рамка для резюме

Два проекта — одна история: **«строю слои изоляции на Linux-примитивах и измеряю их»**. Light-Andromeda — изоляция сети (VPC-overlay, NAT, AF_XDP, 108 Mpps single-core). Sandbox-Executor — изоляция исполнения (namespaces/cgroups/seccomp/NEWTIME, герметичный профиль) + типизированный фидбек для агентов, с опубликованным измерением cost/turns. Оба на Rust, оба с CI и бенчами. Плюс робототехнический плагин (фаза 2) — если цель именно robotics.

---

## 10. Ключевые источники (полные списки с URL — в `raw/`)

- Token economics: Complexity Trap (2508.21433); CoACT (2607.02911); SWE-Pruner Pro (2607.18213); «How Do AI Agents Spend Your Money?» (2604.22750); **Token Reduction Is Not Cost Reduction (2607.12161)**; JetBrains RTK benchmark (Jul 2026); Anthropic code-execution-with-MCP, advanced-tool-use, context-engineering, context-management; LOCA-bench (2602.07962); AgentNoiseBench (2602.11348).
- Feedback form: SWE-agent ACI (2405.15793); RustAssistant (2308.05177); VeriHarness (2607.14167); PGS (2506.18315); FeedbackEval (2504.06939); Fact Selection (2404.05520); Type-Error Ablation (2606.01522); Generative Compilation (2607.13921); Is Three the Magic Number (2607.05197); WilliamT (2505.13103); DebugHarness (2604.03610); CodeRover-S (2411.03346); AutoPatchBench; SEC-bench (2506.11791); CRUST-Bench (2504.15254); Bosch feedback loops (2512.02567); Randomness in Agentic Evals (2602.07150).
- Determinism/systems: Anthropic infrastructure-noise (2026-02-05); Terminal-Bench 2.1; Grounded Scaling (2606.22495); Hermit; Antithesis; DeltaBox (2605.22781); Crab (2604.28138); Sandlock (2605.26298); Bazel linux-sandbox; Firecracker snapshot docs; runc CVEs 2025; SandboxEscapeBench (2603.02277); AgentCgroup (2602.09345).
- Landscape: Modal Series C; Vercel $1M challenge; Docker Sandboxes; K8s agent-sandbox; OpenSandbox; OpenShell; Anthropic sandbox-runtime и «How we contain Claude»; Codex `truncate.rs`; Gemini CLI config; harness inventory (wincent gist).
- Robotics: Eureka (2310.12931); CaP-X (2603.22435); RHO (2606.16458); RATs (2606.19419); ASPIRE (2607.00272); RDA (2606.01672); RoboEval (2311.11183); MuJoCo perf (discussions/1522).
