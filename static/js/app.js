/* Small progressive enhancements for the Atelier UI (PLAN P5.6-P5.8).
   Everything works without JavaScript; this only adds comfort. No inline handlers:
   behaviour is attached through data-* attributes (CSP: script-src 'self'). */
(function () {
  "use strict";

  /* ---- Mobile navigation drawer ------------------------------------------------ */
  function setDrawer(open) {
    var sidebar = document.getElementById("sidebar");
    var backdrop = document.getElementById("sidebar-backdrop");
    var toggle = document.querySelector("[data-nav-toggle]");
    if (!sidebar) return;
    sidebar.classList.toggle("is-open", open);
    if (backdrop) backdrop.hidden = !open;
    if (toggle) toggle.setAttribute("aria-expanded", String(open));
    if (open) {
      var first = sidebar.querySelector("a, button");
      if (first) first.focus();
    }
  }
  document.addEventListener("click", function (event) {
    if (event.target.closest("[data-nav-toggle]")) setDrawer(true);
    else if (event.target.closest("[data-nav-close]")) setDrawer(false);
  });
  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape") {
      setDrawer(false);
      document.querySelectorAll("details.menu[open]").forEach(function (menu) { menu.open = false; });
    }
  });

  /* ---- Dropdown menus (<details class="menu">): close when clicking elsewhere ---- */
  document.addEventListener("click", function (event) {
    document.querySelectorAll("details.menu[open]").forEach(function (menu) {
      if (!menu.contains(event.target)) menu.open = false;
    });
  });

  /* ---- Toasts: dismiss button + auto-hide (errors stay) ------------------------ */
  function initToasts(scope) {
    (scope || document).querySelectorAll(".toast").forEach(function (toast) {
      if (toast.dataset.ready) return;
      toast.dataset.ready = "1";
      var close = toast.querySelector(".toast-close");
      if (close) close.addEventListener("click", function () { toast.remove(); });
      if (!toast.classList.contains("toast-error")) {
        setTimeout(function () { toast.remove(); }, 6000);
      }
    });
  }
  window.showToast = function (message, level) {
    var region = document.getElementById("toasts");
    if (!region) return;
    var toast = document.createElement("div");
    toast.className = "toast toast-" + (level || "info");
    toast.setAttribute("role", level === "error" ? "alert" : "status");
    var body = document.createElement("div");
    body.className = "toast-body";
    body.textContent = message;
    var close = document.createElement("button");
    close.type = "button";
    close.className = "btn btn-ghost btn-icon btn-sm toast-close";
    close.setAttribute("aria-label", "Fermer");
    close.textContent = "×";
    toast.append(body, close);
    region.append(toast);
    initToasts(region);
  };

  /* ---- Confirmations: <form data-confirm="Message" data-confirm-action="Supprimer"> -- */
  var dialog;
  function confirmDialog(form) {
    if (!dialog) {
      dialog = document.createElement("dialog");
      dialog.className = "dialog";
      dialog.innerHTML =
        '<form method="dialog"><div class="dialog-body"><h2 data-title></h2><p class="muted" data-text></p></div>' +
        '<div class="dialog-actions"><button class="btn" value="cancel">Annuler</button>' +
        '<button class="btn btn-primary" value="ok" data-ok></button></div></form>';
      document.body.append(dialog);
    }
    dialog.querySelector("[data-title]").textContent = form.dataset.confirmTitle || "Confirmer";
    dialog.querySelector("[data-text]").textContent = form.dataset.confirm;
    var ok = dialog.querySelector("[data-ok]");
    ok.textContent = form.dataset.confirmAction || "Confirmer";
    ok.className = "btn " + (form.dataset.confirmDanger !== undefined ? "btn-danger btn-solid" : "btn-primary");
    dialog.onclose = function () {
      if (dialog.returnValue === "ok") {
        form.dataset.confirmed = "1";
        form.requestSubmit ? form.requestSubmit(form._submitter) : form.submit();
      }
    };
    dialog.showModal();
  }
  document.addEventListener("submit", function (event) {
    var form = event.target;
    if (!form.dataset.confirm || form.dataset.confirmed) return;
    event.preventDefault();
    form._submitter = event.submitter || null;
    if (typeof HTMLDialogElement === "function") confirmDialog(form);
    else if (window.confirm(form.dataset.confirm)) { form.dataset.confirmed = "1"; form.submit(); }
  });

  /* ---- Double-submit guard ----------------------------------------------------- */
  document.addEventListener("submit", function (event) {
    if (event.defaultPrevented) return;
    var button = event.submitter;
    if (button && button.classList.contains("btn")) {
      setTimeout(function () { button.classList.add("is-loading"); button.disabled = true; }, 0);
    }
  });

  /* ---- File drop zones: show the chosen file name ----------------------------- */
  document.addEventListener("change", function (event) {
    var input = event.target;
    if (!input.matches(".dropzone input[type=file]")) return;
    var label = input.closest(".dropzone").querySelector("[data-file-name]");
    if (label) label.textContent = input.files.length ? input.files[0].name : "";
  });
  ["dragenter", "dragover"].forEach(function (type) {
    document.addEventListener(type, function (event) {
      var zone = event.target.closest && event.target.closest(".dropzone");
      if (zone) zone.classList.add("is-dragover");
    });
  });
  ["dragleave", "drop"].forEach(function (type) {
    document.addEventListener(type, function (event) {
      var zone = event.target.closest && event.target.closest(".dropzone");
      if (zone) zone.classList.remove("is-dragover");
    });
  });

  /* ---- Bulk selection: <input data-select-all="name"> + live counter ----------- */
  document.addEventListener("change", function (event) {
    var input = event.target;
    var name = input.dataset.selectAll;
    var form = input.form || input.closest("form");
    if (!form) return;
    if (name) {
      form.querySelectorAll('input[name="' + name + '"]').forEach(function (box) { box.checked = input.checked; });
    }
    var counter = form.querySelector("[data-selected-count]");
    if (counter) {
      var group = counter.dataset.selectedCount;
      counter.textContent = form.querySelectorAll('input[name="' + group + '"]:checked').length;
    }
  });

  /* ---- Theme switcher: <button data-theme-choice="dark"> ----------------------- */
  document.addEventListener("click", function (event) {
    var button = event.target.closest("[data-theme-choice]");
    if (!button) return;
    var choice = button.dataset.themeChoice;
    document.documentElement.dataset.theme = choice;
    document.querySelectorAll("[data-theme-choice]").forEach(function (b) {
      b.setAttribute("aria-pressed", String(b.dataset.themeChoice === choice));
    });
    try { localStorage.setItem("theme", choice); } catch (e) { /* ignore */ }
    var url = button.dataset.themeUrl;
    var token = document.querySelector('meta[name="csrf-token"]');
    if (url && token) {
      fetch(url, {
        method: "POST",
        headers: { "X-CSRFToken": token.content, "Content-Type": "application/x-www-form-urlencoded" },
        body: "theme=" + encodeURIComponent(choice),
        credentials: "same-origin",
      });
    }
  });

  /* ---- HTMX: toasts from HX-Trigger, re-init swapped content ------------------- */
  document.addEventListener("toast", function (event) {
    var items = event.detail && event.detail.value !== undefined ? event.detail.value : event.detail;
    (Array.isArray(items) ? items : [items]).forEach(function (item) {
      if (item && item.message) window.showToast(item.message, item.level);
    });
  });
  document.addEventListener("htmx:afterSwap", function (event) { initToasts(event.target); });
  document.addEventListener("htmx:responseError", function () {
    window.showToast("Une erreur est survenue. Réessayez.", "error");
  });

  /* ---- Repeating rows: [data-add-row="#tbody"][data-template="#tpl"], [data-remove-row] -- */
  document.addEventListener("click", function (event) {
    var add = event.target.closest("[data-add-row]");
    if (add) {
      var target = document.querySelector(add.dataset.addRow);
      var template = document.querySelector(add.dataset.template);
      if (target && template) {
        target.append(template.content.cloneNode(true));
        var inputs = target.lastElementChild.querySelectorAll("input");
        if (inputs.length) inputs[0].focus();
      }
      return;
    }
    var remove = event.target.closest("[data-remove-row]");
    if (remove) {
      remove.closest("tr").remove();
      updateRubricMean();
    }
    if (event.target.closest("[data-print]")) window.print();
  });

  /* ---- Rubric average (grading page) ------------------------------------------- */
  function updateRubricMean() {
    var output = document.querySelector("[data-rubric-mean]");
    if (!output) return;
    var values = Array.prototype.map.call(document.querySelectorAll(".rubric-score"), function (input) {
      return parseFloat(input.value.replace(",", "."));
    }).filter(function (value) { return !isNaN(value) && value >= 0 && value <= 20; });
    output.textContent = values.length
      ? (values.reduce(function (a, b) { return a + b; }, 0) / values.length).toFixed(2).replace(".", ",")
      : "—";
  }
  document.addEventListener("input", function (event) {
    if (event.target.classList.contains("rubric-score")) updateRubricMean();
  });
  updateRubricMean();

  /* ---- Conditional fields: <div data-show-if="assignment_type=choice_based"> or
          data-show-if="is_team_work" (checkbox). Only hides: values are still submitted
          (the server ignores e.g. team sizes for individual work). ------------------------ */
  function refreshConditional(root) {
    (root || document).querySelectorAll("[data-show-if]").forEach(function (block) {
      var form = block.closest("form");
      if (!form) return;
      var expression = block.dataset.showIf;
      var negate = expression.charAt(0) === "!";
      var rule = (negate ? expression.slice(1) : expression).split("=");
      var field = form.elements[rule[0]];
      if (!field) return;
      var visible;
      if (field.type === "checkbox") visible = field.checked;
      else visible = rule.length > 1 ? field.value === rule[1] : Boolean(field.value);
      if (negate) visible = !visible;
      block.hidden = !visible;
    });
  }
  document.addEventListener("change", function () { refreshConditional(); });
  refreshConditional();

  // Top-bar quick search: HTMX fills #quick-results; arrows move through links,
  // Escape closes, "/" focuses the field from anywhere.
  var quickInput = document.querySelector("[data-quick-search]");
  var quickPanel = document.getElementById("quick-results");
  if (quickInput && quickPanel) {
    var quickLinks = function () { return Array.prototype.slice.call(quickPanel.querySelectorAll("a")); };
    var closeQuick = function () { quickPanel.hidden = true; };
    var openQuick = function () { if (quickPanel.innerHTML.trim()) quickPanel.hidden = false; };
    document.addEventListener("htmx:afterSwap", function (event) {
      if (event.target === quickPanel) {
        quickPanel.hidden = !quickPanel.innerHTML.trim() || document.activeElement !== quickInput;
      }
    });
    quickInput.addEventListener("focus", openQuick);
    quickInput.addEventListener("input", function () { if (quickInput.value.trim().length < 2) closeQuick(); });
    quickInput.form.addEventListener("keydown", function (event) {
      var links = quickLinks();
      var index = links.indexOf(document.activeElement);
      if (event.key === "Escape") {
        if (quickPanel.hidden) return; // second Escape: native clear of the field
        event.preventDefault();
        if (document.activeElement !== quickInput) quickInput.focus();
        closeQuick();
      } else if (event.key === "ArrowDown" || event.key === "ArrowUp") {
        if (quickPanel.hidden || !links.length) return;
        event.preventDefault();
        var step = event.key === "ArrowDown" ? 1 : -1;
        if (index === -1) index = step === 1 ? -1 : links.length;
        var next = index + step;
        if (next < 0) quickInput.focus();
        else links[Math.min(next, links.length - 1)].focus();
      }
    });
    document.addEventListener("click", function (event) {
      if (!quickInput.form.contains(event.target)) closeQuick();
    });
    quickInput.form.addEventListener("focusout", function (event) {
      if (event.relatedTarget && !quickInput.form.contains(event.relatedTarget)) closeQuick();
    });
    document.addEventListener("keydown", function (event) {
      var tag = (event.target.tagName || "").toLowerCase();
      if (event.key === "/" && !event.ctrlKey && !event.metaKey && tag !== "input"
          && tag !== "textarea" && tag !== "select" && !event.target.isContentEditable) {
        event.preventDefault();
        quickInput.focus();
        quickInput.select();
      }
    });
  }

  initToasts();
})();
