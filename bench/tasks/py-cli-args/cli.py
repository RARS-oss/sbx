"""A tiny command-line argument parser (no argparse)."""


def parse_args(argv):
    """Return (flags: dict, positionals: list).

    --name value / --name=value  -> flags['name'] = 'value'
    --verbose (no value)         -> flags['verbose'] = True
    -x                           -> same as --x
    repeated flag                -> last value wins
    '--'                         -> everything after it is positional
    """
    flags = {}
    positionals = []
    i = 0
    while i < len(argv):
        tok = argv[i]
        if tok.startswith("--") and len(tok) > 2:
            name = tok[2:]
            if i + 1 < len(argv) and not argv[i + 1].startswith("-"):
                flags[name] = argv[i + 1]
                i += 2
            else:
                flags[name] = True
                i += 1
        elif tok.startswith("-") and len(tok) > 1:
            name = tok[1:]
            if i + 1 < len(argv) and not argv[i + 1].startswith("-"):
                flags[name] = argv[i + 1]
                i += 2
            else:
                flags[name] = True
                i += 1
        else:
            positionals.append(tok)
            i += 1
    return flags, positionals
