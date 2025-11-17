let allTracks = [];
let filteredTracks = [];
let currentAlbum = "all";
let currentGenre = "all"; // Thêm state cho genre

const gridEl = document.getElementById("grid");
const countLabelEl = document.getElementById("count-label");
const emptyStateEl = document.getElementById("empty-state");
const searchInputEl = document.getElementById("search-input");

const albumFiltersContainer = document.getElementById("album-filters");
const genreFiltersContainer = document.getElementById("genre-filters"); // Container mới

const filterButtonsStaticAlbum = document.querySelectorAll(
    ".filter-chip[data-album]"
);
const filterButtonsStaticGenre = document.querySelectorAll(
    ".filter-chip[data-genre]"
);

function formatTime(sec) {
    if (!sec || isNaN(sec)) return "0:00";
    const m = Math.floor(sec / 60);
    const s = Math.floor(sec % 60)
        .toString()
        .padStart(2, "0");
    return `${m}:${s}`;
}

// --- LOGIC ALBUM ---
function renderAlbums() {
    const albums = Array.from(
        new Set(allTracks.map((t) => t.album).filter(Boolean))
    );

    albumFiltersContainer.innerHTML = "";

    albums.forEach((album) => {
        const btn = document.createElement("button");
        btn.className = "filter-chip";
        btn.dataset.album = album;
        btn.textContent = album;
        btn.addEventListener("click", () => {
            setAlbumFilter(album);
        });
        albumFiltersContainer.appendChild(btn);
    });
}

function setAlbumFilter(album) {
    currentAlbum = album;
    // Reset active class cho album
    document.querySelectorAll(".filter-chip[data-album]").forEach((btn) => {
        const value = btn.dataset.album;
        btn.classList.toggle(
            "active",
            (album === "all" && value === "all") || value === album
        );
    });
    applyFilters();
}

// --- LOGIC GENRE (MỚI) ---
function renderGenres() {
    // Lấy danh sách genre duy nhất. Nếu bài hát không có genre thì để 'Khác' hoặc bỏ qua
    const genres = Array.from(
        new Set(allTracks.map((t) => t.genre || "Khác").filter(Boolean))
    );

    genreFiltersContainer.innerHTML = "";

    genres.forEach((genre) => {
        const btn = document.createElement("button");
        btn.className = "filter-chip";
        btn.dataset.genre = genre;
        btn.textContent = genre;
        btn.addEventListener("click", () => {
            setGenreFilter(genre);
        });
        genreFiltersContainer.appendChild(btn);
    });
}

function setGenreFilter(genre) {
    currentGenre = genre;
    // Reset active class cho genre
    document.querySelectorAll(".filter-chip[data-genre]").forEach((btn) => {
        const value = btn.dataset.genre;
        btn.classList.toggle(
            "active",
            (genre === "all" && value === "all") || value === genre
        );
    });
    applyFilters();
}

// --- LOGIC FILTER CHUNG ---
function applyFilters() {
    const keyword = searchInputEl.value.trim().toLowerCase();

    filteredTracks = allTracks.filter((track) => {
        // Filter Album
        const matchAlbum =
            currentAlbum === "all" || track.album === currentAlbum;

        // Filter Genre (Xử lý trường hợp track không có genre thì gán là 'Khác')
        const trackGenre = track.genre || "Khác";
        const matchGenre =
            currentGenre === "all" || trackGenre === currentGenre;

        // Filter Keyword
        const matchKeyword =
            !keyword ||
            track.title.toLowerCase().includes(keyword) ||
            track.artist.toLowerCase().includes(keyword);

        return matchAlbum && matchGenre && matchKeyword;
    });

    renderGrid();
}

function renderGrid() {
    gridEl.innerHTML = "";

    if (!filteredTracks.length) {
        emptyStateEl.style.display = "block";
        countLabelEl.textContent = "0 bài hát";
        return;
    }

    emptyStateEl.style.display = "none";
    countLabelEl.textContent = `${filteredTracks.length} bài hát`;

    filteredTracks.forEach((track) => {
        const card = document.createElement("article");
        card.className = "card";

        const cardTop = document.createElement("div");
        cardTop.className = "card-top";

        const cover = document.createElement("div");
        cover.className = "card-cover";
        cover.style.backgroundImage = `url('${track.cover_url}')`;

        const meta = document.createElement("div");
        meta.className = "card-meta";

        const title = document.createElement("div");
        title.className = "card-title";
        title.textContent = track.title;

        const artist = document.createElement("div");
        artist.className = "card-artist";
        artist.textContent = track.artist;

        const album = document.createElement("div");
        album.className = "card-album";
        // Hiển thị thêm genre ở đây cho đẹp
        const genreText = track.genre ? ` • ${track.genre}` : "";
        album.textContent =
            (track.album ? track.album : "Single") + genreText;

        meta.appendChild(title);
        meta.appendChild(artist);
        meta.appendChild(album);

        cardTop.appendChild(cover);
        cardTop.appendChild(meta);

        const badges = document.createElement("div");
        badges.className = "card-badges";

        const durationBadge = document.createElement("span");
        durationBadge.className = "badge";
        durationBadge.textContent = `⏱ ${formatTime(track.duration_sec)}`;

        badges.appendChild(durationBadge);

        const cardBottom = document.createElement("div");
        cardBottom.className = "card-bottom";

        const hint = document.createElement("span");
        hint.textContent = "Nhấn để phát";

        // Container chứa các nút hành động
        const actionContainer = document.createElement("div");
        actionContainer.className = "card-actions";

        // Nút Add to Playlist (+)
        const addBtn = document.createElement("button");
        addBtn.className = "icon-btn add";
        addBtn.innerHTML = "+";
        addBtn.title = "Thêm vào playlist";
        addBtn.onclick = (e) => {
            e.stopPropagation(); // Ngăn không cho click lan ra card (không play nhạc)
            alert(`Đã thêm "${track.title}" vào playlist hiện tại!`);
            // Tại đây bạn có thể gọi API để lưu vào DB
        };

        // Nút Play
        const playBtn = document.createElement("button");
        playBtn.className = "icon-btn play";
        playBtn.innerHTML = "▶";

        actionContainer.appendChild(addBtn);
        actionContainer.appendChild(playBtn);

        cardBottom.appendChild(hint);
        cardBottom.appendChild(actionContainer);

        // Sự kiện click card
        card.addEventListener("click", () => {
            window.location.href = "/";
        });

        card.appendChild(cardTop);
        card.appendChild(badges);
        card.appendChild(cardBottom);

        gridEl.appendChild(card);
    });
}

async function init() {
    try {
        const res = await fetch("/api/tracks");
        allTracks = await res.json();
    } catch (e) {
        console.error("Không load được tracks từ backend:", e);
        // Dữ liệu mẫu để test giao diện nếu fetch lỗi
        allTracks = [
            {
                id: 1,
                title: "Midnight Coding",
                artist: "LTX Lo-fi",
                album: "Night Drive",
                genre: "Lo-fi",
                cover_url:
                    "https://images.unsplash.com/photo-1516280440614-6697288d5d38?auto=format&fit=crop&w=200&q=80",
                duration_sec: 182,
            },
            {
                id: 2,
                title: "Pixel Dreams",
                artist: "Synthwave Kids",
                album: "Neon City",
                genre: "Synthwave",
                cover_url:
                    "https://images.unsplash.com/photo-1550745165-9bc0b252726f?auto=format&fit=crop&w=200&q=80",
                duration_sec: 205,
            },
            {
                id: 3,
                title: "Rainy Window",
                artist: "Chillhop Studio",
                album: "Rain Tapes",
                genre: "Chill",
                cover_url:
                    "https://images.unsplash.com/photo-1515694346937-94d85e41e6f0?auto=format&fit=crop&w=200&q=80",
                duration_sec: 194,
            },
            {
                id: 4,
                title: "Cyber Chase",
                artist: "Neo Tokyo",
                album: "Neon City",
                genre: "Synthwave",
                cover_url:
                    "https://images.unsplash.com/photo-1535131749006-b7f58c99034b?auto=format&fit=crop&w=200&q=80",
                duration_sec: 240,
            },
        ];
    }

    renderAlbums();
    renderGenres(); // Render các nút genre

    setAlbumFilter("all");
    setGenreFilter("all");
}

searchInputEl.addEventListener("input", () => {
    applyFilters();
});

// Nút tĩnh "Tất cả"
filterButtonsStaticAlbum.forEach((btn) => {
    btn.addEventListener("click", () => setAlbumFilter("all"));
});
filterButtonsStaticGenre.forEach((btn) => {
    btn.addEventListener("click", () => setGenreFilter("all"));
});

init();