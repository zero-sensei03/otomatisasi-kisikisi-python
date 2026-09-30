"use strict";

document.addEventListener("DOMContentLoaded", () => {
    document.documentElement.classList.add("js-ready");

    initialzeScripts();
    initializeSidebar();
    initializeDropdowns();
    initializeModals();
    initializeAlerts();
});

function initialzeScripts() {

    const forms = document.querySelectorAll(
        "form"
    );

    forms.forEach((form) => {
        form.addEventListener(
            "submit",
            () => {
                const submitButton =
                    form.querySelector(
                        'button[type="submit"]'
                    );

                if (!submitButton) {
                    return;
                }

                submitButton.disabled = true;

                submitButton.dataset.originalText =
                    submitButton.textContent;

                submitButton.textContent =
                    "Memproses...";
            }
        );
    });
}


function initializeSidebar() {
    const sidebar = document.querySelector("[data-sidebar]");
    const overlay = document.querySelector("[data-sidebar-overlay]");
    const openButton = document.querySelector("[data-sidebar-toggle]");
    const closeButton = document.querySelector("[data-sidebar-close]");

    if (!sidebar) {
        return;
    }

    const openSidebar = () => {
        sidebar.classList.add("open");
        overlay?.classList.add("open");

        openButton?.setAttribute("aria-expanded", "true");
    };

    const closeSidebar = () => {
        sidebar.classList.remove("open");
        overlay?.classList.remove("open");

        openButton?.setAttribute("aria-expanded", "false");
    };

    openButton?.addEventListener("click", openSidebar);
    closeButton?.addEventListener("click", closeSidebar);
    overlay?.addEventListener("click", closeSidebar);
}


function initializeDropdowns() {
    const triggers = document.querySelectorAll(
        "[data-dropdown-trigger]"
    );

    triggers.forEach((trigger) => {
        const targetId = trigger.dataset.dropdownTrigger;
        const dropdown = document.getElementById(targetId);

        if (!dropdown) {
            return;
        }

        trigger.addEventListener("click", (event) => {
            event.stopPropagation();

            const isOpen = dropdown.classList.contains("open");

            closeAllDropdowns();

            if (!isOpen) {
                dropdown.classList.add("open");
                trigger.setAttribute("aria-expanded", "true");
            }
        });
    });

    document.addEventListener("click", () => {
        closeAllDropdowns();
    });
}


function closeAllDropdowns() {
    document
        .querySelectorAll("[data-dropdown].open")
        .forEach((dropdown) => {
            dropdown.classList.remove("open");
        });

    document
        .querySelectorAll("[data-dropdown-trigger]")
        .forEach((trigger) => {
            trigger.setAttribute("aria-expanded", "false");
        });
}


function initializeModals() {
    document
        .querySelectorAll("[data-modal]")
        .forEach((modal) => {
            modal
                .querySelectorAll("[data-modal-close]")
                .forEach((element) => {
                    element.addEventListener("click", () => {
                        closeModal(modal);
                    });
                });
        });

    document.addEventListener("keydown", (event) => {
        if (event.key !== "Escape") {
            return;
        }

        document
            .querySelectorAll("[data-modal].open")
            .forEach((modal) => {
                closeModal(modal);
            });
    });
}


function openModal(id) {
    const modal = document.getElementById(id);

    if (!modal) {
        return;
    }

    modal.classList.add("open");
    modal.setAttribute("aria-hidden", "false");

    document.body.style.overflow = "hidden";
}


function closeModal(modalOrId) {
    const modal =
        typeof modalOrId === "string"
            ? document.getElementById(modalOrId)
            : modalOrId;

    if (!modal) {
        return;
    }

    modal.classList.remove("open");
    modal.setAttribute("aria-hidden", "true");

    if (!document.querySelector("[data-modal].open")) {
        document.body.style.overflow = "";
    }
}


function initializeAlerts() {
    document
        .querySelectorAll("[data-dismiss-alert]")
        .forEach((button) => {
            button.addEventListener("click", () => {
                const alert = button.closest(".alert");

                if (alert) {
                    alert.remove();
                }
            });
        });
}