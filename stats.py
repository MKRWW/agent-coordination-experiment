#!/usr/bin/env python3
"""
Fisher-Exact-Test, zweiseitig, ohne externe Abhaengigkeit.

Fuer 2x2-Tafeln  [[a, b], [c, d]]  wird die Wahrscheinlichkeit jeder Tafel mit
denselben Randsummen ueber die hypergeometrische Verteilung berechnet; der
zweiseitige p-Wert ist die Summe aller Tafeln, die hoechstens so
wahrscheinlich sind wie die beobachtete.
"""
from math import comb


def _p_table(a, b, c, d):
    n = a + b + c + d
    return (comb(a + b, a) * comb(c + d, c)) / comb(n, a + c)


def fisher_exact(a, b, c, d):
    """[[a,b],[c,d]] -> (odds_ratio, p_two_sided)"""
    row1, row2 = a + b, c + d
    col1 = a + c
    n = row1 + row2
    p_obs = _p_table(a, b, c, d)
    total = 0.0
    lo = max(0, col1 - row2)
    hi = min(row1, col1)
    for x in range(lo, hi + 1):
        y = row1 - x
        z = col1 - x
        w = row2 - z
        p = _p_table(x, y, z, w)
        if p <= p_obs * (1 + 1e-9):
            total += p
    if b * c == 0:
        odds = float("inf") if a * d > 0 else float("nan")
    else:
        odds = (a * d) / (b * c)
    return odds, min(1.0, total)


def compare_binary(name_1, k1, n1, name_2, k2, n2):
    """Zwei Anteile vergleichen. k = Treffer, n = Stichprobe."""
    odds, p = fisher_exact(k1, n1 - k1, k2, n2 - k2)
    return {"arm_1": name_1, "k1": k1, "n1": n1, "rate_1": k1 / n1 if n1 else None,
            "arm_2": name_2, "k2": k2, "n2": n2, "rate_2": k2 / n2 if n2 else None,
            "odds_ratio": None if odds != odds else (
                "inf" if odds == float("inf") else round(odds, 3)),
            "p_value": p, "p_str": f"{p:.4f}" if p >= 0.0001 else "<0.0001",
            "p_fmt": (f"p={p:.4f}" if p >= 0.0001 else "p<0.0001"),
            "significant_05": p < 0.05}


if __name__ == "__main__":
    # Kontrolle gegen bekannte Werte
    print("Lady tasting tea [[3,1],[1,3]] erwartet p=0.4857 ->",
          f"{fisher_exact(3,1,1,3)[1]:.4f}")
    print("[[10,0],[0,10]] erwartet p<0.0001 ->", f"{fisher_exact(10,0,0,10)[1]:.6f}")
    print("[[3,27],[0,30]] ->", compare_binary("v4",3,30,"hinweis",0,30))
