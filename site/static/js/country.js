/* Country pages: "Compare with…" goes to the canonical /compare/a-vs-b/ page (alphabetical slugs). */
(() => {
  const f = document.querySelector("[data-compare-with]");
  if (!f) return;
  f.addEventListener("submit", e => {
    e.preventDefault();
    const b = f.b.value;
    if (!b) return;
    const [x, y] = [f.dataset.aSlug, b].sort();
    location.href = `/compare/${x}-vs-${y}/`;
  });
  f.b.addEventListener("change", () => f.requestSubmit());
})();
