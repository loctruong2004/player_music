document.addEventListener("DOMContentLoaded", () => {
    const gridEl = document.getElementById("grid");
    const countLabel = document.getElementById("count-label");
    const emptyState = document.getElementById("empty-state");
    const searchInput = document.getElementById("search-input");
    const albumFiltersEl = document.getElementById("album-filters");
    const genreFiltersEl = document.getElementById("genre-filters");
    const paginationEl = document.getElementById("pagination");

    if (!gridEl) {
        console.error(
            "❌ Không tìm thấy #grid trong DOM, kiểm tra lại id='grid'"
        );
        return;
    }

    let allTracks = [];
    let filteredTracks = [];
    let activeAlbum = "all";
    let activeGenre = "all";
    let searchKeyword = "";
    let currentPage = 1;
    const pageSize = 30;

    // ========== FORMAT THỜI GIAN mm:ss ==========
    function formatTime(sec) {
        if (!sec || isNaN(sec)) return "0:00";
        const m = Math.floor(sec / 60);
        const s = Math.floor(sec % 60)
            .toString()
            .padStart(2, "0");
        return `${m}:${s}`;
    }

    // ========== USER CHIP (DÙNG /api/me) ==========
    async function initUserChip() {
        const chip = document.getElementById("user-chip");
        const avatar = document.getElementById("user-avatar");
        const nameSpan = document.getElementById("user-chip-name");

        if (!chip || !avatar || !nameSpan) return;

        try {
            const res = await fetch("/api/me");
            if (!res.ok) {
                nameSpan.textContent = "Guest";
                avatar.textContent = "G";
                return;
            }

            const data = await res.json();
            if (!data.authenticated) {
                nameSpan.textContent = "Guest";
                avatar.textContent = "G";
                return;
            }

            const name = data.name || "User";
            const initial = name.trim().charAt(0).toUpperCase() || "U";
            avatar.textContent = initial;
            nameSpan.textContent = `Xin chào, ${name}`;
        } catch (e) {
            console.error("Lỗi initUserChip (library):", e);
            const nameSpan = document.getElementById("user-chip-name");
            const avatar = document.getElementById("user-avatar");
            if (nameSpan) nameSpan.textContent = "Guest";
            if (avatar) avatar.textContent = "G";
        }
    }

    // ========== FETCH TRACKS TỪ BACKEND ==========
    async function loadTracks() {
        try {
            console.log("🔄 Gọi /api/tracks...");
            const res = await fetch("/api/tracks");

            if (res.status === 401) {
                alert(
                    "⚠️ Phiên đăng nhập đã hết hạn, hệ thống sẽ chuyển bạn về trang đăng nhập."
                );
                window.location.href = "/auth";
                return;
            }

            if (!res.ok) {
                throw new Error(
                    "Không tải được danh sách bài hát, status = " + res.status
                );
            }

            const data = await res.json();
            console.log("✅ Nhận được tracks:", data);
            allTracks = Array.isArray(data) ? data : [];

            buildFilters(allTracks);
            applyFilters();
        } catch (err) {
            console.error("❌ Lỗi loadTracks:", err);
            allTracks = [];
            applyFilters();
        }
    }
    // ========= USER CHIP LOGIC =========
    const userChip = document.getElementById("user-chip");
    const userAvatar = document.getElementById("user-avatar");
    const userChipName = document.getElementById("user-chip-name");
    const userMenu = document.getElementById("user-menu");
    const userMenuEmail = document.getElementById("user-menu-email");

    async function initUserChip() {
        try {
            const res = await fetch("/api/me");
            if (!res.ok) {
                console.warn("Không lấy được /api/me:", res.status);
                userChipName.textContent = "Guest";
                userAvatar.textContent = "G";
                return;
            }
            const data = await res.json();
            if (!data.authenticated) {
                userChipName.textContent = "Guest";
                userAvatar.textContent = "G";
                return;
            }

            const name = data.name || "User";
            const email = data.email || "";

            const initial = name.trim().charAt(0).toUpperCase() || "U";
            userAvatar.textContent = initial;
            userChipName.textContent = name;
            userMenuEmail.textContent = email;
        } catch (e) {
            console.error("Lỗi initUserChip:", e);
            userChipName.textContent = "Guest";
            userAvatar.textContent = "G";
        }
    }

    userChip.addEventListener("click", (e) => {
        e.stopPropagation();
        userMenu.classList.toggle("open");
    });

    window.addEventListener("click", () => {
        userMenu.classList.remove("open");
    });

    userMenu.addEventListener("click", (e) => {
        e.stopPropagation();
    });
    // ========== TẠO FILTER ALBUM & GENRE ==========
    function buildFilters(tracks) {
        // Album
        const albumSet = new Set();
        tracks.forEach((t) => {
            const albumName = (t.album || t.genre || "").trim();
            if (albumName) albumSet.add(albumName);
        });

        albumFiltersEl.innerHTML = "";
        albumSet.forEach((albumName) => {
            const btn = document.createElement("button");
            btn.className = "filter-chip";
            btn.dataset.album = albumName;
            btn.textContent = albumName;
            albumFiltersEl.appendChild(btn);
        });

        // Genre
        const genreSet = new Set();
        tracks.forEach((t) => {
            const g = (t.genre || "").trim();
            if (g) genreSet.add(g);
        });

        genreFiltersEl.innerHTML = "";
        genreSet.forEach((g) => {
            const btn = document.createElement("button");
            btn.className = "filter-chip";
            btn.dataset.genre = g;
            btn.textContent = g;
            genreFiltersEl.appendChild(btn);
        });

        // Gán event cho filter album
        document.querySelectorAll("[data-album]").forEach((btn) =>
            btn.addEventListener("click", () => {
                document
                    .querySelectorAll("[data-album]")
                    .forEach((b) => b.classList.remove("active"));
                btn.classList.add("active");
                activeAlbum = btn.dataset.album;
                currentPage = 1;
                applyFilters();
            })
        );

        // Gán event cho filter genre
        document.querySelectorAll("[data-genre]").forEach((btn) =>
            btn.addEventListener("click", () => {
                document
                    .querySelectorAll("[data-genre]")
                    .forEach((b) => b.classList.remove("active"));
                btn.classList.add("active");
                activeGenre = btn.dataset.genre;
                currentPage = 1;
                applyFilters();
            })
        );
    }

    // ========== HÀM ÁP DỤNG BỘ LỌC ==========
    function applyFilters() {
        const keyword = searchKeyword.trim().toLowerCase();
        const activeAlbumLower =
            activeAlbum === "all" ? "all" : activeAlbum.toLowerCase();
        const activeGenreLower =
            activeGenre === "all" ? "all" : activeGenre.toLowerCase();

        filteredTracks = allTracks.filter((t) => {
            const title = (t.title || "").toLowerCase();
            const artist = (t.artist || "").toLowerCase();
            const albumName = (t.album || t.genre || "").trim();
            const genreName = (t.genre || "").trim();

            const albumLower = albumName.toLowerCase();
            const genreLower = genreName.toLowerCase();

            const matchSearch =
                !keyword || title.includes(keyword) || artist.includes(keyword);

            const matchAlbum =
                activeAlbumLower === "all" || albumLower === activeAlbumLower;

            const matchGenre =
                activeGenreLower === "all" || genreLower === activeGenreLower;

            return matchSearch && matchAlbum && matchGenre;
        });

        renderCurrentPage();
    }

    // ========== RENDER THEO TRANG ==========
    function renderCurrentPage() {
        const total = filteredTracks.length;
        const totalPages = Math.max(1, Math.ceil(total / pageSize));

        // Nếu currentPage > totalPages (vd sau khi filter), đưa về trang cuối
        if (currentPage > totalPages) currentPage = totalPages;
        if (currentPage < 1) currentPage = 1;

        const startIndex = (currentPage - 1) * pageSize;
        const endIndex = startIndex + pageSize;
        const pageItems = filteredTracks.slice(startIndex, endIndex);

        renderTracks(pageItems);

        countLabel.textContent =
            total === 0
                ? "0 bài hát"
                : `${total} bài hát · Trang ${currentPage}/${totalPages}`;

        emptyState.style.display = total === 0 ? "block" : "none";
        renderPagination(totalPages, total);
    }

    // ========== RENDER CARD ==========
    function createTrackCard(track) {
        const card = document.createElement("div");
        card.className = "card";
        card.dataset.trackId = track.id;

        const coverUrl =
            track.cover_url && track.cover_url.trim() !== ""
                ? track.cover_url
                : "/static/default_cover.jpg";

        const albumName = track.album || track.genre || "Single";
        const duration = track.duration_sec || 0;
        const durationLabel = formatTime(duration);
        const genre = track.genre || "Unknown";

        card.innerHTML = `
            <div class="card-top">
              <div class="card-cover" style="background-image:url('${coverUrl}')"></div>
              <div class="card-meta">
                <div>
                  <div class="card-title" title="${escapeHtml(
            track.title || ""
        )}">${escapeHtml(track.title || "")}</div>
                  <div class="card-artist" title="${escapeHtml(
            track.artist || ""
        )}">${escapeHtml(track.artist || "")}</div>
                  <div class="card-album">${escapeHtml(albumName)}</div>
                </div>
                <div class="card-badges">
                  <span class="badge">${escapeHtml(genre)}</span>
                </div>
                <div class="card-bottom">
                  <span>${durationLabel}</span>
                  <div class="card-actions">
                    <button class="icon-btn play" data-track-id="${track.id
            }">▶</button>
                    <button class="icon-btn add" data-track-id="${track.id
            }">＋</button>
                  </div>
                </div>
              </div>
            </div>
          `;

        // Gắn event trực tiếp
        const addBtn = card.querySelector(".icon-btn.add");
        const playBtn = card.querySelector(".icon-btn.play");

        if (addBtn) {
            addBtn.addEventListener("click", async (e) => {
                e.stopPropagation();
                const id = addBtn.dataset.trackId;
                console.log("🟢 Click ADD track_id =", id);
                if (!id) return;
                await addToPlaylist(id);
            });
        }

        if (playBtn) {
            playBtn.addEventListener("click", async (e) => {
                e.stopPropagation();
                const id = playBtn.dataset.trackId;
                console.log("🟢 Click PLAY track_id =", id);
                if (!id) return;
                await playAndGoToPlayer(id);
            });
        }

        // Click cả card = play
        card.addEventListener("click", async () => {
            const id = card.dataset.trackId;
            console.log("🟢 Click CARD track_id =", id);
            if (!id) return;
            await playAndGoToPlayer(id);
        });

        return card;
    }

    function renderTracks(tracks) {
        gridEl.innerHTML = "";
        tracks.forEach((t) => {
            const card = createTrackCard(t);
            gridEl.appendChild(card);
        });
    }

    // helper escape html
    function escapeHtml(str) {
        return String(str)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    // ========== RENDER PAGINATION ==========
    function renderPagination(totalPages, totalItems) {
        if (!paginationEl) return;

        // Nếu không có hoặc chỉ 1 trang thì ẩn pagination
        if (totalItems === 0 || totalPages <= 1) {
            paginationEl.style.display = "none";
            paginationEl.innerHTML = "";
            return;
        }

        paginationEl.style.display = "flex";
        paginationEl.innerHTML = "";

        // Prev button
        const prevBtn = document.createElement("button");
        prevBtn.className =
            "page-btn" + (currentPage === 1 ? " disabled" : "");
        prevBtn.textContent = "‹";
        prevBtn.title = "Trang trước";
        if (currentPage > 1) {
            prevBtn.addEventListener("click", () => {
                currentPage -= 1;
                renderCurrentPage();
            });
        }
        paginationEl.appendChild(prevBtn);

        // Tạo list page number (đơn giản: hiển thị tối đa 7 nút: 1,2,...,n)
        const maxButtons = 7;
        let startPage = Math.max(1, currentPage - 3);
        let endPage = Math.min(totalPages, startPage + maxButtons - 1);
        // Điều chỉnh nếu ở cuối
        if (endPage - startPage + 1 < maxButtons) {
            startPage = Math.max(1, endPage - maxButtons + 1);
        }

        if (startPage > 1) {
            createPageButton(1);
            if (startPage > 2) {
                const dots = document.createElement("span");
                dots.textContent = "...";
                dots.className = "page-info";
                paginationEl.appendChild(dots);
            }
        }

        for (let p = startPage; p <= endPage; p++) {
            createPageButton(p);
        }

        if (endPage < totalPages) {
            if (endPage < totalPages - 1) {
                const dots = document.createElement("span");
                dots.textContent = "...";
                dots.className = "page-info";
                paginationEl.appendChild(dots);
            }
            createPageButton(totalPages);
        }

        // Next button
        const nextBtn = document.createElement("button");
        nextBtn.className =
            "page-btn" + (currentPage === totalPages ? " disabled" : "");
        nextBtn.textContent = "›";
        nextBtn.title = "Trang sau";
        if (currentPage < totalPages) {
            nextBtn.addEventListener("click", () => {
                currentPage += 1;
                renderCurrentPage();
            });
        }
        paginationEl.appendChild(nextBtn);
    }

    function createPageButton(page) {
        const btn = document.createElement("button");
        btn.className = "page-btn" + (page === currentPage ? " active" : "");
        btn.textContent = page;
        btn.dataset.page = page;
        if (page !== currentPage) {
            btn.addEventListener("click", () => {
                currentPage = page;
                renderCurrentPage();
            });
        }
        paginationEl.appendChild(btn);
    }

    // ========== EVENT: SEARCH ==========
    searchInput.addEventListener("input", (e) => {
        searchKeyword = e.target.value || "";
        currentPage = 1;
        applyFilters();
    });

    // ========== HÀM GỌI API ==========
    async function playAndGoToPlayer(trackId) {
        try {
            console.log("📡 Gửi API add-track + play cho track", trackId);

            await fetch("/api/playlists/add-track", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ track_id: Number(trackId) }),
            });

            await fetch("/api/player/play", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ track_id: Number(trackId) }),
            });
        } catch (err) {
            console.error("❌ Lỗi khi playAndGoToPlayer:", err);
        }

        window.location.href = "/?track_id=" + encodeURIComponent(trackId);
    }

    async function addToPlaylist(trackId) {
        try {
            console.log(
                "📡 Gửi API /api/playlists/add-track cho track",
                trackId
            );
            const res = await fetch("/api/playlists/add-track", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ track_id: Number(trackId) }),
            });

            if (!res.ok) {
                console.error("❌ addToPlaylist status =", res.status);
                if (res.status === 401) {
                    alert("⚠️ Bạn chưa đăng nhập, hãy login lại.");
                } else {
                    alert("⚠️ Request thất bại: " + res.status);
                }
                return;
            }

            const data = await res.json();
            console.log("✅ Kết quả addToPlaylist:", data);

            if (data.duplicated) {
                alert("ℹ️ Bài hát này đã có trong playlist rồi!");
            } else {
                alert("✅ Đã thêm bài hát vào playlist của bạn!");
            }
        } catch (err) {
            console.error("❌ Lỗi addToPlaylist:", err);
            alert(
                "⚠️ Thêm vào playlist thất bại, xem console để biết chi tiết."
            );
        }
    }

    // ========== KHỞI TẠO ==========
    initUserChip();
    loadTracks();
});