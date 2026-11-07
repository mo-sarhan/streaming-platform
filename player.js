const video = document.getElementById("video");
const qualitySelect = document.getElementById("quality");

const videoId = 9;

let hls = null;
let bufferMonitor = null;


// ==========================================
// 1. Load Video Information
// ==========================================

async function loadVideo() {
    try {
        console.log("Loading video...");

        const response = await fetch(
            `http://127.0.0.1:8000/videos/${videoId}/play`
        );

        if (!response.ok) {
            throw new Error(`Playback API error: ${response.status}`);
        }

        const data = await response.json();

        console.log("Video information:", data);

        const playlistUrl =data["playback_url"]

        initializePlayer(playlistUrl);

    } catch (error) {
        console.error("Failed to load video:", error);
    }
}


// ==========================================
// 2. Initialize HLS Player
// ==========================================

function initializePlayer(playlistUrl) {

    if (Hls.isSupported()) {

        hls = new Hls({
            debug: false
        });

        hls.loadSource(playlistUrl);
        hls.attachMedia(video);


        // ==========================================
        // 3. Master Playlist Loaded
        // ==========================================

        hls.on(Hls.Events.MANIFEST_PARSED, () => {

            console.log("Master playlist loaded.");

            populateQualityOptions();

            // Enable automatic quality selection.
            hls.currentLevel = -1;

            startBufferMonitoring();

        });


        // ==========================================
        // 4. Quality Switching
        // ==========================================

        hls.on(Hls.Events.LEVEL_SWITCHED, (event, data) => {

            const level = hls.levels[data.level];

            console.log("Quality switched:", {
                height: level.height,
                width: level.width,
                bitrate: level.bitrate
            });

        });


        // ==========================================
        // 5. Segment Loading
        // ==========================================

        hls.on(Hls.Events.FRAG_LOADING, (event, data) => {

            console.log("Loading segment:", {
                segment: data.frag.sn,
                url: data.frag.url
            });

        });


        // ==========================================
        // 6. Segment Downloaded
        // ==========================================

        hls.on(Hls.Events.FRAG_LOADED, (event, data) => {

            console.log("Segment downloaded:", {
                segment: data.frag.sn,
                duration: data.frag.duration,
                bandwidthEstimate: hls.bandwidthEstimate,
                currentQuality: hls.currentLevel
            });

        });


        // ==========================================
        // 7. HLS Errors
        // ==========================================

        hls.on(Hls.Events.ERROR, (event, data) => {

            console.error("HLS error:", data);

            if (!data.fatal) return;

            switch (data.type) {

                case Hls.ErrorTypes.NETWORK_ERROR:

                    console.error("Network error. Recovering...");

                    hls.startLoad();

                    break;


                case Hls.ErrorTypes.MEDIA_ERROR:

                    console.error("Media error. Recovering...");

                    hls.recoverMediaError();

                    break;


                default:

                    console.error("Unrecoverable HLS error.");

                    stopBufferMonitoring();

                    hls.destroy();

                    hls = null;

                    break;

            }

        });

    }

    // ==========================================
    // Native HLS Support (Safari)
    // ==========================================

    else if (video.canPlayType("application/vnd.apple.mpegurl")) {

        video.src = playlistUrl;

    }

    else {

        console.error("This browser does not support HLS.");

    }

}


// ==========================================
// 8. Populate Quality Selector
// ==========================================

function populateQualityOptions() {

    qualitySelect.innerHTML = '<option value="-1">Auto</option>';

    hls.levels.forEach((level, index) => {

        const option = document.createElement("option");

        option.value = index;

        option.textContent = `${level.height}p`;

        qualitySelect.appendChild(option);

        console.log("Available quality:", {
            index,
            height: level.height,
            width: level.width,
            bitrate: level.bitrate
        });

    });

}


// ==========================================
// 9. Manual Quality Selection
// ==========================================

qualitySelect.addEventListener("change", () => {

    if (!hls) return;

    const selectedLevel = Number(qualitySelect.value);

    hls.currentLevel = selectedLevel;

    if (selectedLevel === -1) {

        console.log("Automatic quality selection enabled.");

    } else {

        console.log(
            `Manual quality selected: ${hls.levels[selectedLevel].height}p`
        );

    }

});


// ==========================================
// 10. Buffer Monitoring
// ==========================================

function monitorBuffer() {

    if (!video || video.buffered.length === 0) {
        return;
    }

    const currentTime = video.currentTime;

    // Find the buffered range containing the current playback position.
    let bufferedEnd = null;

    for (let i = 0; i < video.buffered.length; i++) {

        const start = video.buffered.start(i);
        const end = video.buffered.end(i);

        if (currentTime >= start && currentTime <= end) {

            bufferedEnd = end;
            break;

        }

    }

    if (bufferedEnd === null) {

        console.log("Current position is not buffered.");

        return;

    }

    const bufferDuration = bufferedEnd - currentTime;

    console.log("Buffer status:", {
        currentTime: currentTime.toFixed(2),
        bufferedUntil: bufferedEnd.toFixed(2),
        bufferDuration: bufferDuration.toFixed(2),
        estimatedBandwidth: hls
            ? `${(hls.bandwidthEstimate / 1_000_000).toFixed(2)} Mbps`
            : "Unknown"
    });

}


// ==========================================
// 11. Start Buffer Monitoring
// ==========================================

function startBufferMonitoring() {

    stopBufferMonitoring();

    bufferMonitor = setInterval(() => {

        monitorBuffer();

    }, 2000);

}


// ==========================================
// 12. Stop Buffer Monitoring
// ==========================================

function stopBufferMonitoring() {

    if (bufferMonitor !== null) {

        clearInterval(bufferMonitor);

        bufferMonitor = null;

    }

}


// ==========================================
// 13. Video Events
// ==========================================

video.addEventListener("playing", () => {

    console.log("Video is playing.");

});


video.addEventListener("waiting", () => {

    console.warn("Buffer exhausted. Waiting for more data...");

});


video.addEventListener("stalled", () => {

    console.warn("Video download stalled.");

});


video.addEventListener("seeking", () => {

    console.log("Seeking to:", video.currentTime);

});


video.addEventListener("seeked", () => {

    console.log("Seek completed:", video.currentTime);

});


video.addEventListener("ended", () => {

    console.log("Video playback completed.");

    stopBufferMonitoring();

});


// ==========================================
// 14. Start Player
// ==========================================

loadVideo();


// ==========================================
// 15. Cleanup
// ==========================================

window.addEventListener("beforeunload", () => {

    stopBufferMonitoring();

    if (hls) {

        hls.destroy();

        hls = null;

    }

});
