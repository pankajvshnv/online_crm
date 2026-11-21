document.addEventListener(
    "DOMContentLoaded",
    function () {
        document
            .querySelectorAll(
                '[data-bs-toggle="tooltip"]'
            )
            .forEach(
                function (element) {
                    new bootstrap.Tooltip(
                        element
                    );
                }
            );

        document.addEventListener(
            "click",
            function (event) {
                const activityButton =
                    event.target.closest(
                        "[data-activity-modal]"
                    );

                if (!activityButton) {
                    return;
                }

                const modalId =
                    activityButton.dataset
                        .activityModal;

                const modalElement =
                    document.getElementById(
                        modalId
                    );

                if (!modalElement) {
                    return;
                }

                const tooltip =
                    bootstrap.Tooltip
                        .getInstance(
                            activityButton
                        );

                if (tooltip) {
                    tooltip.hide();
                }

                bootstrap.Modal
                    .getOrCreateInstance(
                        modalElement
                    )
                    .show();
            }
        );
    }
);
