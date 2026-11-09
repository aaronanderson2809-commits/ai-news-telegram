/**
 * PERSONAL AI NEWS INTELLIGENCE - FRONTEND APPLICATION CONTROLLER (ES6)
 * Works 100% standalone via file:// protocol without requiring a web server.
 */

(function () {
    "use strict";

    // State
    const state = {
        category: "ALL",
        searchQuery: "",
        dateRange: "ALL",
        specificDate: "",
        sentiment: "ALL",
        sortBy: "date_desc"
    };

    // DOM Elements
    let searchInput, categorySelect, dateSelect, specificDateInput, sentimentSelect, sortSelect;
    let navPills, statCards, categorySections, resultCounterEl;

    function initApp() {
        searchInput = document.getElementById("filter-search");
        categorySelect = document.getElementById("filter-category");
        dateSelect = document.getElementById("filter-date-range");
        specificDateInput = document.getElementById("filter-specific-date");
        sentimentSelect = document.getElementById("filter-sentiment");
        sortSelect = document.getElementById("filter-sort");
        resultCounterEl = document.getElementById("active-filter-count");

        navPills = Array.from(document.querySelectorAll(".nav-pill"));
        statCards = Array.from(document.querySelectorAll(".stat-card"));
        categorySections = Array.from(document.querySelectorAll(".category-section"));

        bindEvents();
        applyFiltersAndSort();
    }

    function bindEvents() {
        if (searchInput) {
            searchInput.addEventListener("input", function (e) {
                state.searchQuery = e.target.value.trim().toLowerCase();
                applyFiltersAndSort();
            });
        }

        if (categorySelect) {
            categorySelect.addEventListener("change", function (e) {
                setCategory(e.target.value);
            });
        }

        if (dateSelect) {
            dateSelect.addEventListener("change", function (e) {
                state.dateRange = e.target.value;
                if (state.dateRange !== "CUSTOM" && specificDateInput) {
                    specificDateInput.value = "";
                    state.specificDate = "";
                }
                applyFiltersAndSort();
            });
        }

        if (specificDateInput) {
            specificDateInput.addEventListener("change", function (e) {
                state.specificDate = e.target.value;
                if (state.specificDate && dateSelect) {
                    state.dateRange = "CUSTOM";
                    dateSelect.value = "CUSTOM";
                } else if (dateSelect) {
                    state.dateRange = "ALL";
                    dateSelect.value = "ALL";
                }
                applyFiltersAndSort();
            });
        }

        if (sentimentSelect) {
            sentimentSelect.addEventListener("change", function (e) {
                state.sentiment = e.target.value;
                applyFiltersAndSort();
            });
        }

        if (sortSelect) {
            sortSelect.addEventListener("change", function (e) {
                state.sortBy = e.target.value;
                applyFiltersAndSort();
            });
        }

        // Category Nav Pills
        navPills.forEach(function (pill) {
            pill.addEventListener("click", function () {
                const cat = pill.getAttribute("data-category") || "ALL";
                setCategory(cat);
            });
        });

        // Dashboard Stat Cards
        statCards.forEach(function (card) {
            card.addEventListener("click", function () {
                const cat = card.getAttribute("data-category") || "ALL";
                setCategory(cat);
                const newsAnchor = document.getElementById("news-categories-anchor");
                if (newsAnchor) {
                    newsAnchor.scrollIntoView({ behavior: "smooth" });
                }
            });
        });

        // Keyword chips inside news cards
        document.querySelectorAll(".keyword-chip").forEach(function (chip) {
            chip.addEventListener("click", function () {
                const kw = chip.getAttribute("data-keyword") || chip.textContent.trim();
                if (searchInput) {
                    searchInput.value = kw;
                    state.searchQuery = kw.toLowerCase();
                    applyFiltersAndSort();
                    searchInput.focus();
                }
            });
        });

        // Reset Button
        const resetBtn = document.getElementById("btn-reset-filters");
        if (resetBtn) {
            resetBtn.addEventListener("click", resetFilters);
        }

        // Regenerate Modal Buttons
        const regenBtn = document.getElementById("btn-regenerate-report");
        const closeModalBtn = document.getElementById("btn-close-modal");
        const modalBackdrop = document.getElementById("regenerate-modal");
        const copyCmdBtn = document.getElementById("btn-copy-cli");
        const triggerServerBtn = document.getElementById("btn-trigger-local-api");

        if (regenBtn && modalBackdrop) {
            regenBtn.addEventListener("click", function () {
                modalBackdrop.classList.add("open");
            });
        }
        if (closeModalBtn && modalBackdrop) {
            closeModalBtn.addEventListener("click", function () {
                modalBackdrop.classList.remove("open");
            });
        }
        if (modalBackdrop) {
            modalBackdrop.addEventListener("click", function (e) {
                if (e.target === modalBackdrop) {
                    modalBackdrop.classList.remove("open");
                }
            });
        }
        if (copyCmdBtn) {
            copyCmdBtn.addEventListener("click", function () {
                const cmdText = document.getElementById("cli-command-text").textContent.trim();
                if (navigator.clipboard) {
                    navigator.clipboard.writeText(cmdText);
                    copyCmdBtn.textContent = "Berhasil Disalin ✓";
                    setTimeout(function () {
                        copyCmdBtn.textContent = "Salin Perintah CLI";
                    }, 2000);
                }
            });
        }
        if (triggerServerBtn) {
            triggerServerBtn.addEventListener("click", function () {
                const statusEl = document.getElementById("regen-api-status");
                statusEl.textContent = "Menghubungi local automation server (http://127.0.0.1:8765/api/regenerate)...";
                fetch("http://127.0.0.1:8765/api/regenerate", { method: "POST" })
                    .then(function (r) { return r.json(); })
                    .then(function (data) {
                        statusEl.textContent = "Laporan berhasil diperbarui! Memuat ulang halaman...";
                        setTimeout(function () { window.location.reload(); }, 1200);
                    })
                    .catch(function () {
                        statusEl.textContent = "Info: File HTML dibuka langsung tanpa daemon server aktif. Silakan jalankan perintah CLI di atas pada terminal Anda untuk mengambil berita terbaru.";
                    });
            });
        }
    }

    function setCategory(cat) {
        state.category = cat;
        if (categorySelect) {
            categorySelect.value = cat;
        }
        navPills.forEach(function (pill) {
            const pCat = pill.getAttribute("data-category") || "ALL";
            pill.classList.toggle("active", pCat === cat);
        });
        statCards.forEach(function (card) {
            const cCat = card.getAttribute("data-category") || "ALL";
            card.classList.toggle("active-stat", cCat === cat);
        });
        applyFiltersAndSort();
    }

    function resetFilters() {
        state.category = "ALL";
        state.searchQuery = "";
        state.dateRange = "ALL";
        state.specificDate = "";
        state.sentiment = "ALL";
        state.sortBy = "date_desc";

        if (searchInput) searchInput.value = "";
        if (categorySelect) categorySelect.value = "ALL";
        if (dateSelect) dateSelect.value = "ALL";
        if (specificDateInput) specificDateInput.value = "";
        if (sentimentSelect) sentimentSelect.value = "ALL";
        if (sortSelect) sortSelect.value = "date_desc";

        setCategory("ALL");
    }

    function matchesDateFilter(pubDateStr) {
        if (!pubDateStr) return true;
        if (state.dateRange === "ALL" && !state.specificDate) return true;

        if (state.specificDate) {
            return pubDateStr === state.specificDate;
        }

        const articleDate = new Date(pubDateStr + "T00:00:00");
        if (isNaN(articleDate.getTime())) return true;

        // Reference report generation date or current date
        const reportDateAttr = document.body.getAttribute("data-report-date");
        const refDate = reportDateAttr ? new Date(reportDateAttr + "T23:59:59") : new Date();
        const diffDays = (refDate - articleDate) / (1000 * 60 * 60 * 24);

        if (state.dateRange === "TODAY") {
            return diffDays <= 1.2 && diffDays >= -1;
        }
        if (state.dateRange === "2DAYS") {
            return diffDays <= 2.5 && diffDays >= -1;
        }
        if (state.dateRange === "7DAYS") {
            return diffDays <= 7.5 && diffDays >= -1;
        }
        return true;
    }

    function applyFiltersAndSort() {
        let totalVisible = 0;

        categorySections.forEach(function (section) {
            const secCat = section.getAttribute("data-category-section");
            const cardsContainer = section.querySelector(".news-cards-grid");
            const cards = Array.from(section.querySelectorAll(".news-card"));
            const countBadge = section.querySelector(".category-banner-count");

            // Check if category section itself is filtered out
            const categoryMatch = (state.category === "ALL" || state.category === secCat);
            if (!categoryMatch) {
                section.style.display = "none";
                return;
            }

            let visibleInSection = 0;

            cards.forEach(function (card) {
                const searchBlob = (card.getAttribute("data-search") || "").toLowerCase();
                const pubDate = card.getAttribute("data-date") || "";
                const sentiment = card.getAttribute("data-sentiment") || "Netral";

                const matchesSearch = !state.searchQuery || searchBlob.indexOf(state.searchQuery) !== -1;
                const matchesDate = matchesDateFilter(pubDate);
                const matchesSentiment = (state.sentiment === "ALL" || state.sentiment === sentiment);

                if (matchesSearch && matchesDate && matchesSentiment) {
                    card.style.display = "flex";
                    visibleInSection += 1;
                    totalVisible += 1;
                } else {
                    card.style.display = "none";
                }
            });

            // Sort cards within this category container
            cards.sort(function (a, b) {
                const tsA = a.getAttribute("data-timestamp") || "";
                const tsB = b.getAttribute("data-timestamp") || "";
                const scoreA = parseFloat(a.getAttribute("data-sentiment-score") || "0");
                const scoreB = parseFloat(b.getAttribute("data-sentiment-score") || "0");
                const srcA = (a.getAttribute("data-source") || "").toLowerCase();
                const srcB = (b.getAttribute("data-source") || "").toLowerCase();

                if (state.sortBy === "date_desc") {
                    return tsB.localeCompare(tsA);
                }
                if (state.sortBy === "date_asc") {
                    return tsA.localeCompare(tsB);
                }
                if (state.sortBy === "sentiment_pos") {
                    return scoreB - scoreA || tsB.localeCompare(tsA);
                }
                if (state.sortBy === "sentiment_neg") {
                    return scoreA - scoreB || tsB.localeCompare(tsA);
                }
                if (state.sortBy === "source_asc") {
                    return srcA.localeCompare(srcB) || tsB.localeCompare(tsA);
                }
                return 0;
            });

            cards.forEach(function (card) {
                cardsContainer.appendChild(card);
            });

            if (countBadge) {
                countBadge.textContent = visibleInSection + " Berita Ditampilkan";
            }

            section.style.display = visibleInSection > 0 ? "block" : "none";
        });

        if (resultCounterEl) {
            resultCounterEl.textContent = totalVisible;
        }

        const emptyStateEl = document.getElementById("empty-filter-state");
        if (emptyStateEl) {
            emptyStateEl.style.display = totalVisible === 0 ? "block" : "none";
        }
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", initApp);
    } else {
        initApp();
    }
})();

