/* Trusted demo adapter for compiled executable conformance.
 * The policy is not proven *by* this source; every reachable action is checked
 * against the independently audited policy graph by binary_contract.py.
 */
#include <stdio.h>
#include <string.h>
#include <stdlib.h>

static int read_int(const char *line, const char *name, int *out) {
  char needle[64];
  snprintf(needle, sizeof(needle), "\"%s\":", name);
  const char *position = strstr(line, needle);
  if (!position) return 0;
  return sscanf(position + strlen(needle), "%d", out) == 1;
}
static int read_action(const char *line, char action[32]) {
  const char *p = strstr(line, "\"action\":\"");
  if (!p) return 0;
  return sscanf(p, "\"action\":\"%31[^\"]\"", action) == 1;
}

int main(void) {
  char buffer[4096];
  while (fgets(buffer, sizeof(buffer), stdin)) {
    int buyer, escrow, seller, refunded, settled;
    char act[32] = {0};
    if (!read_int(buffer, "buyer", &buyer) || !read_int(buffer, "escrow", &escrow) ||
        !read_int(buffer, "seller", &seller) || !read_int(buffer, "refunded", &refunded) ||
        !read_int(buffer, "settled", &settled) || !read_action(buffer, act)) {
      puts("{\"rejected\":true}"); continue;
    }
    if (strcmp(act, "reserve") == 0 && escrow == 0 && settled == 0 && refunded == 0 && buyer >= 1) {
      buyer--; escrow++;
    } else if (strcmp(act, "settle") == 0 && escrow == 1 && settled == 0) {
      escrow--;
#ifdef BAD_ESCROW
      seller += 2;
#else
      seller++;
#endif
      settled = 1;
    } else if (strcmp(act, "refund") == 0 && escrow == 1 && refunded == 0) {
      escrow--; buyer++; refunded = 1;
    } else {
      puts("{\"rejected\":true}"); continue;
    }
    printf("{\"state\":{\"buyer\":%d,\"escrow\":%d,\"seller\":%d,\"settled\":%d,\"refunded\":%d}}\n",
            buyer, escrow, seller, settled, refunded);
  }
  return 0;
}
