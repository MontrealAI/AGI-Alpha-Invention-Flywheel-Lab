"""Freeze the two routes using development scores only, inside the public sandbox."""


def choose(development):
    def lowest(scores):
        return min(scores, key=lambda name: (scores[name]["object_mae"], -scores[name]["within_tolerance"], name))
    return {"cross_band_weight": lowest(development["correction"]), "gp_setting": lowest(development["gp"])}
