#include <iostream>
#include <string>
#include <vector>

// Count '#' among the 8 neighbours of each cell; outside the grid counts as '.'.
static int neighbours(const std::vector<std::string>& g, int r, int c) {
    int rows = static_cast<int>(g.size());
    int cols = static_cast<int>(g[0].size());
    int n = 0;
    for (int dr = -1; dr <= 1; ++dr) {
        for (int dc = -1; dc <= 1; ++dc) {
            if (dr == 0 && dc == 0) continue;
            int rr = r + dr, cc = c + dc;
            if (rr < 0 || rr >= rows || cc < 0 || cc >= cols) continue;
            if (g[rr][cc] == '#') ++n;
        }
    }
    return n;
}

int main() {
    int rows, cols;
    if (!(std::cin >> rows >> cols) || rows <= 0 || cols <= 0) return 2;
    std::vector<std::string> g(rows);
    for (int r = 0; r < rows; ++r) {
        std::cin >> g[r];
        if (static_cast<int>(g[r].size()) != cols) return 3;
    }
    for (int r = 0; r < rows; ++r) {
        std::string line;
        for (int c = 0; c < cols; ++c) line += static_cast<char>('0' + neighbours(g, r, c));
        std::cout << line << '\n';
    }
    return 0;
}
