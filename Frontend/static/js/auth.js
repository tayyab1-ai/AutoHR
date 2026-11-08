document.addEventListener("DOMContentLoaded", function () {
  var btn = document.querySelector("[data-google-sign-in]");
  if (!btn) return;
  btn.addEventListener("click", function () {
    btn.setAttribute("aria-busy", "true");
    btn.classList.add("opacity-75");
  });
});
