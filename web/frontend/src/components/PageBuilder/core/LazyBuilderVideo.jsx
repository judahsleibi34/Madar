import { useEffect, useRef, useState } from "react";
import { Maximize2, Pause, Play, Volume2, VolumeX } from "lucide-react";

const formatTime = (seconds) => {
  const safeSeconds = Number.isFinite(seconds) ? Math.max(0, Math.floor(seconds)) : 0;
  const minutes = Math.floor(safeSeconds / 60);
  return `${minutes}:${String(safeSeconds % 60).padStart(2, "0")}`;
};

const LazyBuilderVideo = ({
  src,
  controls = true,
  muted = false,
  loop = false,
  className = "",
  style,
  "aria-label": ariaLabel,
  ...props
}) => {
  const containerRef = useRef(null);
  const videoRef = useRef(null);
  const [shouldLoad, setShouldLoad] = useState(false);
  const [isPlaying, setIsPlaying] = useState(false);
  const [isMuted, setIsMuted] = useState(muted);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);

  useEffect(() => {
    const node = videoRef.current;
    if (!node || typeof IntersectionObserver === "undefined") {
      setShouldLoad(true);
      return undefined;
    }

    const observer = new IntersectionObserver(([entry]) => {
      if (entry?.isIntersecting) {
        setShouldLoad(true);
        return;
      }
      // Stop decoding off-screen frames while retaining the loaded metadata.
      if (!node.paused) node.pause();
    }, { rootMargin: "120px 0px" });

    observer.observe(node);
    return () => observer.disconnect();
  }, [src]);

  const togglePlayback = async () => {
    const video = videoRef.current;
    if (!video) return;
    if (video.paused) {
      try {
        await video.play();
      } catch {
        setIsPlaying(false);
      }
    } else {
      video.pause();
    }
  };

  const toggleMuted = () => {
    const video = videoRef.current;
    if (!video) return;
    video.muted = !video.muted;
    setIsMuted(video.muted);
  };

  const seek = (event) => {
    const video = videoRef.current;
    const nextTime = Number(event.target.value);
    if (!video || !Number.isFinite(nextTime)) return;
    video.currentTime = nextTime;
    setCurrentTime(nextTime);
  };

  const enterFullscreen = async () => {
    const container = containerRef.current;
    if (!container) return;
    if (document.fullscreenElement) {
      await document.exitFullscreen?.();
      return;
    }
    await container.requestFullscreen?.();
  };

  const stopEditorInteraction = (event) => event.stopPropagation();
  const progress = duration > 0 ? Math.min(100, (currentTime / duration) * 100) : 0;

  return (
    <div
      ref={containerRef}
      {...props}
      className={`${className} modern-video-player ${isPlaying ? "is-playing" : "is-paused"}`.trim()}
      style={style}
    >
      <video
        ref={videoRef}
        className="modern-video-media"
        src={shouldLoad ? src : undefined}
        muted={isMuted}
        loop={loop}
        playsInline
        preload={shouldLoad ? "metadata" : "none"}
        controlsList="nodownload"
        aria-label={ariaLabel}
        onClick={controls ? togglePlayback : undefined}
        onLoadedMetadata={(event) => setDuration(event.currentTarget.duration || 0)}
        onDurationChange={(event) => setDuration(event.currentTarget.duration || 0)}
        onTimeUpdate={(event) => setCurrentTime(event.currentTarget.currentTime || 0)}
        onPlay={() => setIsPlaying(true)}
        onPause={() => setIsPlaying(false)}
        onEnded={() => setIsPlaying(false)}
      />

      {controls && (
        <div className="modern-video-ui" onClick={stopEditorInteraction} onPointerDown={stopEditorInteraction}>
          {!isPlaying && (
            <button className="modern-video-center-play" type="button" onClick={togglePlayback} aria-label="Play video">
              <Play size={24} fill="currentColor" />
            </button>
          )}

          <div className="modern-video-controls">
            <button type="button" onClick={togglePlayback} aria-label={isPlaying ? "Pause video" : "Play video"}>
              {isPlaying ? <Pause size={18} fill="currentColor" /> : <Play size={18} fill="currentColor" />}
            </button>
            <span className="modern-video-time">{formatTime(currentTime)}</span>
            <input
              className="modern-video-progress"
              type="range"
              min="0"
              max={duration || 0}
              step="0.01"
              value={Math.min(currentTime, duration || 0)}
              onChange={seek}
              aria-label="Video progress"
              style={{ "--video-progress": `${progress}%` }}
            />
            <span className="modern-video-time">{formatTime(duration)}</span>
            <button type="button" onClick={toggleMuted} aria-label={isMuted ? "Unmute video" : "Mute video"}>
              {isMuted ? <VolumeX size={18} /> : <Volume2 size={18} />}
            </button>
            <button type="button" onClick={enterFullscreen} aria-label="Toggle fullscreen">
              <Maximize2 size={18} />
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default LazyBuilderVideo;
