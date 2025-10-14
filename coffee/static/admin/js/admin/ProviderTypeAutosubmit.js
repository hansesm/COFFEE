document.addEventListener("DOMContentLoaded", function () {
  const select = document.getElementById("id_type");
  if (!select) return;
  select.addEventListener("change", function () {
    this.form.submit();
  });
});