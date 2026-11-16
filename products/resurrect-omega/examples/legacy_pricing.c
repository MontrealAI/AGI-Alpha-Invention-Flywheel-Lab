/* Public synthetic legacy pricing oracle. Trusted demonstration fixture only.
 * The reconstruction process sees only the compiled executable and its outputs.
 * JSONL protocol: region, seats, tier -> subtotal_cents/tax_cents/total_cents.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int main(void) {
  char line[4096];
  while (fgets(line, sizeof(line), stdin) != NULL) {
    char region[16] = {0}, tier[16] = {0};
    int seats = 0;
    char *r = strstr(line, "\"region\":");
    char *s = strstr(line, "\"seats\":");
    char *t = strstr(line, "\"tier\":");
    if (!r || !s || !t ||
        sscanf(r, "\"region\":\"%15[^\"]\"", region) != 1 ||
        sscanf(s, "\"seats\":%d", &seats) != 1 ||
        sscanf(t, "\"tier\":\"%15[^\"]\"", tier) != 1) {
      puts("{\"error\":\"invalid_request\"}");
      continue;
    }
    if (seats < 1 || seats > 4 ||
        (strcmp(region, "NA") && strcmp(region, "EU") && strcmp(region, "APAC")) ||
        (strcmp(tier, "BASIC") && strcmp(tier, "PRO"))) {
      puts("{\"error\":\"outside_contract\"}");
      continue;
    }
    int base = strcmp(tier, "PRO") == 0 ? 2500 : 900;
    int subtotal = base * seats;
    if (seats >= 3) subtotal -= base / 2;
    int tax_rate = strcmp(region, "EU") == 0 ? 13 : (strcmp(region, "APAC") == 0 ? 7 : 0);
    int tax = (subtotal * tax_rate + 50) / 100;
    printf("{\"subtotal_cents\":%d,\"tax_cents\":%d,\"total_cents\":%d}\n", subtotal, tax, subtotal + tax);
  }
  return 0;
}
