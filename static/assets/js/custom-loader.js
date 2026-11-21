(function () {
    var isHidden = false;

    function hideLoader() {
        if (isHidden) {
            return;
        }

        var loader = document.getElementById("crm-page-loader");
        if (!loader) {
            return;
        }

        isHidden = true;
        loader.classList.add("is-hidden");

        window.setTimeout(function () {
            loader.style.display = "none";
        }, 200);
    }

    if (document.readyState === "interactive" || document.readyState === "complete") {
        hideLoader();
    } else {
        document.addEventListener("DOMContentLoaded", hideLoader);
    }

    window.addEventListener("load", hideLoader);
    window.addEventListener("pageshow", hideLoader);

    // Guaranteed fallback after 300ms maximum
    window.setTimeout(hideLoader, 300);
})();
