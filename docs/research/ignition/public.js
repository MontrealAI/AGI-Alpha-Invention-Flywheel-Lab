"use strict";

(() => {
  const measures = {
    complete: {
      en: ["8.005 s → 8.005 s", "Mean whole-reader CPU time on the sparse panel. The original and patched readers tied. No beneficiary speedup or payment was established."],
      fr: ["8,005 s → 8,005 s", "Temps moyen de lecture complète sur processeur pour le panneau peu dense. Les deux versions sont à égalité. Aucun gain pour le bénéficiaire ni aucun paiement n’a été établi."]
    },
    step: {
      en: ["208.27 → 92.82 ms", "Summed median normalization time across 24 windows. Two windows accounted for 98.73% of the gain."],
      fr: ["208,27 → 92,82 ms", "Somme des temps médians de normalisation pour 24 fenêtres. Deux fenêtres représentaient 98,73 % du gain."]
    }
  };
  const query = new URLSearchParams(location.search);
  let saved;
  try { saved = localStorage.getItem("ignition-language"); } catch {}
  const languages = ["en", "fr"];
  const initial = [query.get("lang"), saved, navigator.language.slice(0, 2)].find(code => languages.includes(code)) || "en";
  let activeLanguage;

  function measure() {
    const selected = document.querySelector('input[name="metric"]:checked');
    if (!selected) return;
    const [result, description] = measures[selected.value][activeLanguage];
    document.getElementById("measurement").textContent = result;
    document.getElementById("interpretation").textContent = description;
    document.querySelector(".chart").classList.toggle("step", selected.value === "step");
  }

  function switchLanguage(code, remember) {
    activeLanguage = code;
    document.documentElement.lang = code;
    for (const element of document.querySelectorAll("[data-en][data-fr]")) element.textContent = element.dataset[code];
    for (const language of languages) document.getElementById(language).setAttribute("aria-pressed", String(code === language));
    for (const link of document.querySelectorAll('a[href]')) {
      const destination = new URL(link.href);
      if (destination.origin !== location.origin || !/\/(index|demo)\.html$/.test(destination.pathname)) continue;
      destination.searchParams.set("lang", code);
      link.href = destination.href;
    }
    if (remember) {
      try { localStorage.setItem("ignition-language", code); } catch {}
      const url = new URL(location.href);
      url.searchParams.set("lang", code);
      history.replaceState(null, "", url);
    }
    measure();
  }

  for (const language of languages) document.getElementById(language).addEventListener("click", () => switchLanguage(language, true));
  for (const input of document.querySelectorAll('input[name="metric"]')) input.addEventListener("change", measure);
  switchLanguage(initial, false);
})();
