let tracks = [];

async function initTracks() {
    const errorEl = document.getElementById("playlist-error");
    errorEl.textContent = "";
    try {
        const res = await fetch("/api/my-playlist"); // ✅ gọi API theo user

        if (res.status === 401) {
            // chưa đăng nhập -> đá về trang login
            window.location.href = "/auth";
            return;
        }

        if (!res.ok) {
            errorEl.textContent =
                "Không load được playlist: " + res.status + " " + res.statusText;
            console.error("Lỗi /api/my-playlist:", res.status, res.statusText);
            return;
        }

        tracks = await res.json();
        console.log("Tracks từ backend:", tracks);

        if (!Array.isArray(tracks) || tracks.length === 0) {
            errorEl.textContent = "Không có bài hát trong playlist của bạn.";
        } else {
            // Đổi text trên header thành tên playlist
            const topTitleSpan = document.querySelector(
                ".top-title span:last-child"
            );
            if (topTitleSpan && tracks[0].playlist_name) {
                topTitleSpan.textContent = tracks[0].playlist_name;
            }
        }

        renderPlaylist();
        if (tracks.length > 0) {
            // lần đầu load: chọn bài đầu nhưng không tự play
            loadTrack(0, false);
        }
    } catch (e) {
        errorEl.textContent =
            "Lỗi kết nối tới /api/my-playlist. Xem console để biết chi tiết.";
        console.error("Không load được tracks từ backend:", e);
    }
}

const trackListEl = document.getElementById("track-list");
const audioEl = document.getElementById("audio");
const coverArtEl = document.getElementById("cover-art");
const statusLabelEl = document.getElementById("status-label");
const mainTitleEl = document.getElementById("main-title");
const mainArtistEl = document.getElementById("main-artist");
const albumPillEl = document.getElementById("album-pill");
const durationPillEl = document.getElementById("duration-pill");
const playBtn = document.getElementById("play-btn");
const prevBtn = document.getElementById("prev-btn");
const nextBtn = document.getElementById("next-btn");
const seekBar = document.getElementById("seek-bar");
const currentTimeEl = document.getElementById("current-time");
const totalTimeEl = document.getElementById("total-time");
const volumeBar = document.getElementById("volume-bar");

let currentIndex = 0;
let isPlaying = false;
let seekDragging = false;

audioEl.volume = parseFloat(volumeBar.value);

function formatTime(sec) {
    if (isNaN(sec)) return "0:00";
    const m = Math.floor(sec / 60);
    const s = Math.floor(sec % 60)
        .toString()
        .padStart(2, "0");
    return `${m}:${s}`;
}

function renderPlaylist() {
    trackListEl.innerHTML = "";
    tracks.forEach((track, index) => {
        const li = document.createElement("li");
        li.className = "track-item";
        li.dataset.index = index;

        const thumb = document.createElement("div");
        thumb.className = "track-thumb";
        thumb.style.backgroundImage = `url('${track.cover_url}')`;

        const meta = document.createElement("div");
        meta.className = "track-meta";

        const title = document.createElement("div");
        title.className = "track-title";
        title.textContent = track.title;

        const artist = document.createElement("div");
        artist.className = "track-artist";
        artist.textContent = track.artist || "Unknown";

        meta.appendChild(title);
        meta.appendChild(artist);

        // Khối bên phải: thời lượng + nút xóa
        const rightBox = document.createElement("div");
        rightBox.style.display = "flex";
        rightBox.style.flexDirection = "column";
        rightBox.style.alignItems = "flex-end";
        rightBox.style.gap = "4px";

        const duration = document.createElement("div");
        duration.className = "track-duration";
        duration.textContent = formatTime(track.duration_sec || 0);

        const removeBtn = document.createElement("button");
        removeBtn.className = "track-remove-btn";
        removeBtn.type = "button"; // ✅ rất quan trọng
        removeBtn.textContent = "✕";
        removeBtn.title = "Xóa khỏi playlist";

        // Click nút XÓA – không cho lan lên li
        removeBtn.addEventListener("click", async (e) => {
            e.stopPropagation();
            e.preventDefault(); // ✅ chặn mọi default action (submit form, v.v.)

            console.log(
                "👉 Click nút XÓA track_id =",
                track.id,
                "index =",
                index
            );
            await removeFromPlaylist(track.id, index);
        });

        rightBox.appendChild(duration);
        rightBox.appendChild(removeBtn);

        // Click cả dòng = play bài đó
        li.addEventListener("click", () => {
            loadTrack(index, true);
        });

        li.appendChild(thumb);
        li.appendChild(meta);
        li.appendChild(rightBox);

        trackListEl.appendChild(li);
    });
    refreshActiveTrack();
}

async function removeFromPlaylist(trackId, index) {
    if (!tracks.length) return;

    const confirmDelete = confirm(
        "Bạn có chắc muốn xóa bài này khỏi playlist?"
    );
    if (!confirmDelete) return;

    // nhớ lại bài đang phát trước khi xóa
    const currentTrackId = tracks[currentIndex]?.id;
    const wasPlaying = isPlaying;

    try {
        console.log(
            "📡 Gửi API /api/playlists/remove-track cho track",
            trackId
        );

        const res = await fetch("/api/playlists/remove-track", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ track_id: Number(trackId) }),
        });

        if (res.status === 401) {
            alert("⚠️ Phiên đăng nhập đã hết hạn, vui lòng login lại.");
            window.location.href = "/auth";
            return;
        }

        if (!res.ok) {
            console.error("❌ removeFromPlaylist status =", res.status);
            alert("⚠️ Xóa khỏi playlist thất bại: " + res.status);
            return;
        }

        const data = await res.json();
        console.log("✅ Kết quả removeFromPlaylist:", data);

        // Cập nhật danh sách client side
        tracks.splice(index, 1);

        if (tracks.length === 0) {
            // Hết bài trong playlist
            audioEl.pause();
            audioEl.src = "";
            isPlaying = false;
            playBtn.innerHTML = "&#9658;";
            statusLabelEl.textContent = "Đang dừng";
            mainTitleEl.textContent = "Không còn bài nào trong playlist";
            mainArtistEl.textContent = "";
            albumPillEl.textContent = "Album • N/A";
            durationPillEl.textContent = "⏱ 0:00";
            totalTimeEl.textContent = "0:00";
            currentTimeEl.textContent = "0:00";
            seekBar.value = 0;
        } else {
            // Thử giữ nguyên bài đang phát nếu còn trong playlist
            const stillIndex = tracks.findIndex((t) => t.id === currentTrackId);

            if (stillIndex !== -1) {
                // Bài đang phát vẫn còn trong playlist
                currentIndex = stillIndex;
                loadTrack(currentIndex, wasPlaying);
            } else {
                // Bài đang phát đã bị xóa -> nhảy sang bài kế tiếp hoặc bài trước gần nhất
                if (index < tracks.length) {
                    currentIndex = index; // xóa giữa/list → sang bài kế tiếp
                } else {
                    currentIndex = tracks.length - 1; // xóa cuối → lùi về bài trước
                }
                loadTrack(currentIndex, wasPlaying);
            }
        }

        // Rerender lại sidebar
        renderPlaylist();
    } catch (err) {
        console.error("❌ Lỗi removeFromPlaylist:", err);
        alert("⚠️ Không xóa được bài hát, xem console để biết chi tiết.");
    }
}

function refreshActiveTrack() {
    [...trackListEl.children].forEach((li, idx) => {
        li.classList.toggle("active", idx === currentIndex);
    });
}

function loadTrack(index, autoPlay = false) {
    if (!tracks.length) return;
    currentIndex = index;
    const track = tracks[currentIndex];
    console.log("Load track:", track);

    // Nếu audio_url không có -> báo lỗi nhẹ, không set src
    if (!track.audio_url) {
        console.warn("Track không có audio_url:", track);
        statusLabelEl.textContent = "Không tìm thấy file audio";
        return;
    }

    audioEl.src = track.audio_url;
    audioEl.currentTime = 0;

    coverArtEl.style.backgroundImage = `url('${track.cover_url}')`;
    mainTitleEl.textContent = track.title || "Untitled";
    mainArtistEl.textContent = track.artist || "Unknown Artist";
    albumPillEl.textContent = `Album • ${track.album || track.genre || "N/A"
        }`;
    durationPillEl.textContent = `⏱ ${formatTime(track.duration_sec || 0)}`;
    totalTimeEl.textContent = formatTime(track.duration_sec || 0);

    seekBar.value = 0;
    currentTimeEl.textContent = "0:00";

    audioEl.onloadedmetadata = () => {
        const d = audioEl.duration;
        if (!isNaN(d) && isFinite(d)) {
            totalTimeEl.textContent = formatTime(d);
            durationPillEl.textContent = `⏱ ${formatTime(d)}`;
        }
    };

    refreshActiveTrack();

    if (autoPlay) playTrack();
    else pauseTrack();
}

function playTrack() {
    if (!audioEl.src && tracks.length > 0) {
        loadTrack(0, false);
    }
    audioEl.play().catch((err) => console.error("Lỗi play():", err));
    isPlaying = true;
    playBtn.innerHTML = "&#10074;&#10074;";
    statusLabelEl.textContent = "Đang phát";
}

function pauseTrack() {
    audioEl.pause();
    isPlaying = false;
    playBtn.innerHTML = "&#9658;";
    statusLabelEl.textContent = "Đang dừng";
}

playBtn.addEventListener("click", () => {
    if (isPlaying) pauseTrack();
    else playTrack();
});

prevBtn.addEventListener("click", () => {
    if (!tracks.length) return;
    const newIndex = (currentIndex - 1 + tracks.length) % tracks.length;
    loadTrack(newIndex, true);
});

nextBtn.addEventListener("click", () => {
    if (!tracks.length) return;
    const newIndex = (currentIndex + 1) % tracks.length;
    loadTrack(newIndex, true);
});

audioEl.addEventListener("timeupdate", () => {
    if (!seekDragging && tracks.length) {
        const current = audioEl.currentTime;
        const duration =
            audioEl.duration || tracks[currentIndex].duration_sec || 1;
        const percent = (current / duration) * 100;
        seekBar.value = percent;
        currentTimeEl.textContent = formatTime(current);
    }
});

audioEl.addEventListener("ended", () => {
    if (!tracks.length) return;
    const newIndex = (currentIndex + 1) % tracks.length;
    loadTrack(newIndex, true);
});

// Nếu file audio lỗi (404, path sai...) → báo text để bạn dễ debug
audioEl.addEventListener("error", () => {
    console.error("⚠️ Lỗi khi load audio:", audioEl.src);
    statusLabelEl.textContent =
        "Không phát được file audio (kiểm tra 404 / đường dẫn).";
});

seekBar.addEventListener("input", () => {
    seekDragging = true;
});

seekBar.addEventListener("change", () => {
    if (!tracks.length) return;
    const percent = seekBar.value;
    const duration =
        audioEl.duration || tracks[currentIndex].duration_sec || 1;
    const newTime = (percent / 100) * duration;
    audioEl.currentTime = newTime;
    seekDragging = false;
});

volumeBar.addEventListener("input", () => {
    audioEl.volume = parseFloat(volumeBar.value);
});

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
// ========= END USER CHIP LOGIC =========

initUserChip();
initTracks();