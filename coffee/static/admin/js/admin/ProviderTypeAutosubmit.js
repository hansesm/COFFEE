document.addEventListener("DOMContentLoaded", () => {
  const select = document.getElementById("id_type");
  if (!select) return;

  const help = document.getElementById("id_config_helptext")
           || document.querySelector(".field-config .help")
           || document.querySelector("#id_config")?.closest(".form-row, .form-row.field-config, .field-config")?.querySelector(".help");

  if (!help) return;

  const dataEl = document.getElementById("schema-help-data");
  if (!dataEl) return;

  let map = {};
  try { map = JSON.parse(dataEl.textContent || "{}"); } catch {}

  function updateHelp() {
    const t = select.value;
    help.innerHTML = map[t] || map["_fallback"] || "";
  }

  updateHelp();
  select.addEventListener("change", updateHelp);
});