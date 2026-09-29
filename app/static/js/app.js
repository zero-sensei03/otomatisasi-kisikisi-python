document.addEventListener("DOMContentLoaded", () => {
    const pageLoading = document.getElementById(
        "page-loading"
    );

    const showPageLoading = () => {
        if (!pageLoading) {
            return;
        }

        pageLoading.classList.add("is-visible");
        pageLoading.setAttribute(
            "aria-hidden",
            "false"
        );
    };

    const loadingForms = document.querySelectorAll(
        ".loading-form"
    );

    loadingForms.forEach((form) => {
        form.addEventListener("submit", (event) => {
            if (
                form.classList.contains("delete-form")
            ) {
                const confirmed = window.confirm(
                    "Apakah kamu yakin ingin menghapus data ini?"
                );

                if (!confirmed) {
                    event.preventDefault();
                    return;
                }
            }

            const button = form.querySelector(
                ".loading-button"
            );

            if (button) {
                button.classList.add(
                    "is-loading"
                );

                button.disabled = true;
            }

            showPageLoading();
        });
    });

    const navigationLinks =
        document.querySelectorAll(
            "a[href]:not([target='_blank'])"
        );

    navigationLinks.forEach((link) => {
        link.addEventListener("click", () => {
            const href = link.getAttribute("href");

            if (
                !href ||
                href.startsWith("#") ||
                href.startsWith("javascript:")
            ) {
                return;
            }

            showPageLoading();
        });
    });

    console.log(
        "Tesis Evaluasi initialized."
    );
});
