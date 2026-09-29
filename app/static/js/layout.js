/**
 * =========================================================
 * Tesis Evaluasi - Application JavaScript
 * =========================================================
 */

"use strict";


/**
 * =========================================================
 * DOM READY
 * =========================================================
 */

document.addEventListener("DOMContentLoaded", () => {
    initializeDropdowns();
    initializeMobileMenu();
    initializeLoadingForms();
    initializeNavigationLoading();
});


/**
 * =========================================================
 * DROPDOWN
 * =========================================================
 */

function initializeDropdowns() {

    const dropdowns = document.querySelectorAll(
        ".navbar-dropdown"
    );

    if (!dropdowns.length) {
        return;
    }


    dropdowns.forEach((dropdown) => {

        const button = dropdown.querySelector(
            ".navbar-dropdown-button"
        );

        if (!button) {
            return;
        }


        button.addEventListener("click", (event) => {

            event.stopPropagation();

            const isOpen = dropdown.classList.contains(
                "open"
            );


            closeAllDropdowns();


            if (!isOpen) {

                dropdown.classList.add("open");

                button.setAttribute(
                    "aria-expanded",
                    "true"
                );

            }

        });

    });


    document.addEventListener("click", () => {
        closeAllDropdowns();
    });

}


/**
 * Close all dropdowns.
 */

function closeAllDropdowns() {

    const dropdowns = document.querySelectorAll(
        ".navbar-dropdown"
    );


    dropdowns.forEach((dropdown) => {

        dropdown.classList.remove("open");


        const button = dropdown.querySelector(
            ".navbar-dropdown-button"
        );


        if (button) {

            button.setAttribute(
                "aria-expanded",
                "false"
            );

        }

    });

}


/**
 * =========================================================
 * MOBILE MENU
 * =========================================================
 */

function initializeMobileMenu() {

    const menuButton = document.getElementById(
        "mobile-menu-button"
    );

    const navbarMenu = document.getElementById(
        "navbar-menu"
    );

    const overlay = document.getElementById(
        "sidebar-overlay"
    );


    if (
        !menuButton ||
        !navbarMenu ||
        !overlay
    ) {
        return;
    }


    menuButton.addEventListener(
        "click",
        () => {

            const isOpen =
                menuButton.classList.contains(
                    "active"
                );


            if (isOpen) {
                closeMobileMenu();
            } else {
                openMobileMenu();
            }

        }
    );


    overlay.addEventListener(
        "click",
        () => {
            closeMobileMenu();
        }
    );


    document.addEventListener(
        "keydown",
        (event) => {

            if (event.key === "Escape") {

                closeMobileMenu();
                closeAllDropdowns();

            }

        }
    );


    const menuLinks = navbarMenu.querySelectorAll(
        "a"
    );


    menuLinks.forEach((link) => {

        link.addEventListener(
            "click",
            () => {

                closeMobileMenu();

            }
        );

    });


    window.addEventListener(
        "resize",
        () => {

            if (window.innerWidth > 820) {
                closeMobileMenu();
            }

        }
    );

}


/**
 * Open mobile menu.
 */

function openMobileMenu() {

    const menuButton = document.getElementById(
        "mobile-menu-button"
    );

    const navbarMenu = document.getElementById(
        "navbar-menu"
    );

    const overlay = document.getElementById(
        "sidebar-overlay"
    );


    if (
        !menuButton ||
        !navbarMenu ||
        !overlay
    ) {
        return;
    }


    menuButton.classList.add("active");

    navbarMenu.classList.add("mobile-open");

    overlay.classList.add("active");


    menuButton.setAttribute(
        "aria-expanded",
        "true"
    );

    overlay.setAttribute(
        "aria-hidden",
        "false"
    );


    document.body.style.overflow = "hidden";

}


/**
 * Close mobile menu.
 */

function closeMobileMenu() {

    const menuButton = document.getElementById(
        "mobile-menu-button"
    );

    const navbarMenu = document.getElementById(
        "navbar-menu"
    );

    const overlay = document.getElementById(
        "sidebar-overlay"
    );


    if (
        !menuButton ||
        !navbarMenu ||
        !overlay
    ) {
        return;
    }


    menuButton.classList.remove("active");

    navbarMenu.classList.remove("mobile-open");

    overlay.classList.remove("active");


    menuButton.setAttribute(
        "aria-expanded",
        "false"
    );

    overlay.setAttribute(
        "aria-hidden",
        "true"
    );


    document.body.style.overflow = "";

}


/**
 * =========================================================
 * FORM LOADING
 * =========================================================
 */

function initializeLoadingForms() {

    const forms = document.querySelectorAll(
        ".loading-form"
    );


    forms.forEach((form) => {

        form.addEventListener(
            "submit",
            () => {

                const button =
                    form.querySelector(
                        ".loading-button"
                    );


                if (!button) {
                    return;
                }


                button.classList.add(
                    "loading"
                );


                button.disabled = true;

            }
        );

    });

}


/**
 * =========================================================
 * NAVIGATION LOADING
 * =========================================================
 */

function initializeNavigationLoading() {

    const loading = document.getElementById(
        "page-loading"
    );


    if (!loading) {
        return;
    }


    const links = document.querySelectorAll(
        "a[href]"
    );


    links.forEach((link) => {

        link.addEventListener(
            "click",
            (event) => {

                const href =
                    link.getAttribute("href");


                if (!href) {
                    return;
                }


                /*
                 * Jangan tampilkan loading untuk:
                 * - anchor
                 * - javascript
                 * - external URL
                 * - target baru
                 * - download
                 */

                if (
                    href.startsWith("#") ||
                    href.startsWith("javascript:") ||
                    link.target === "_blank" ||
                    link.hasAttribute("download")
                ) {
                    return;
                }


                const url = new URL(
                    link.href,
                    window.location.href
                );


                if (
                    url.origin !==
                    window.location.origin
                ) {
                    return;
                }


                event.preventDefault();


                showPageLoading();


                window.setTimeout(
                    () => {
                        window.location.href =
                            link.href;
                    },
                    100
                );

            }
        );

    });

}


/**
 * =========================================================
 * PAGE LOADING
 * =========================================================
 */

function showPageLoading() {

    const loading =
        document.getElementById(
            "page-loading"
        );


    if (!loading) {
        return;
    }


    loading.classList.add("active");


    loading.setAttribute(
        "aria-hidden",
        "false"
    );

}


/**
 * Hide page loading.

 * Bisa dipakai dari halaman lain:
 *
 * hidePageLoading();
 */

function hidePageLoading() {

    const loading =
        document.getElementById(
            "page-loading"
        );


    if (!loading) {
        return;
    }


    loading.classList.remove("active");


    loading.setAttribute(
        "aria-hidden",
        "true"
    );

}


/**
 * =========================================================
 * BROWSER BACK / FORWARD
 * =========================================================
 */

window.addEventListener(
    "pageshow",
    () => {

        hidePageLoading();

    }
);