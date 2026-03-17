import { useEffect, useRef, useState } from "react";

export interface PriorityWarning {
  type: "head_movement" | "face_not_detected" | "face_covered" | "tab_switched" | "window_switched" | "fullscreen_exited" | "copy_paste";
  message: string;
  timestamp: number;
}

export function useInterviewProctor(enabled: boolean = true) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const [currentWarning, setCurrentWarning] = useState<PriorityWarning | null>(null);
  const [violations, setViolations] = useState<PriorityWarning[]>([]);
  const detectorRef = useRef<any | null>(null);
  const runningRef = useRef(true);

  // Head movement tracking
  useEffect(() => {
    if (!enabled || typeof window === "undefined") return;

    let detector: any = null;
    let running = true;
    let stream: MediaStream | null = null;

    const startHeadTracking = async () => {
      try {
        // dynamic imports to avoid SSR issues
        const tf = await import("@tensorflow/tfjs");
        await import("@tensorflow/tfjs-backend-webgl");
        await tf.setBackend("webgl");
        await tf.ready();

        const faceLandmarks = await import("@tensorflow-models/face-landmarks-detection");

        detector = await faceLandmarks.createDetector(
          faceLandmarks.SupportedModels.MediaPipeFaceMesh,
          {
            runtime: "tfjs",
            refineLandmarks: true,
          }
        );

        detectorRef.current = detector;

        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) return;
        stream = await navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 480 } });

        if (videoRef.current) {
          videoRef.current.srcObject = stream;
          // eslint-disable-next-line @typescript-eslint/ban-ts-comment
          // @ts-ignore
          await videoRef.current.play();
        }

        const detect = async () => {
          if (!running || !videoRef.current || !detector) return;

          const faces = await detector.estimateFaces(videoRef.current as HTMLVideoElement);

          if (!faces || faces.length === 0) {
            const warning: PriorityWarning = {
              type: "face_not_detected",
              message: "⚠️ Face not detected",
              timestamp: Date.now(),
            };
            setCurrentWarning(warning);
            setViolations((prev) => [...prev, warning]);
            requestAnimationFrame(detect);
            return;
          }

          const keypoints = faces[0].keypoints as any[];
          const nose = keypoints[1];
          const leftEye = keypoints[33];
          const rightEye = keypoints[263];

          if (!nose || !leftEye || !rightEye) {
            const warning: PriorityWarning = {
              type: "face_covered",
              message: "⚠️ Face partially covered",
              timestamp: Date.now(),
            };
            setCurrentWarning(warning);
            setViolations((prev) => [...prev, warning]);
            requestAnimationFrame(detect);
            return;
          }

          const leftDist = Math.abs(nose.x - leftEye.x);
          const rightDist = Math.abs(rightEye.x - nose.x);
          const ratio = leftDist / rightDist;
          const centerY = (videoRef.current as HTMLVideoElement).videoHeight / 2;
          const verticalOffset = Math.abs(nose.y - centerY);

          if (ratio > 1.4 || ratio < 0.7 || verticalOffset > 90) {
            const warning: PriorityWarning = {
              type: "head_movement",
              message: ratio > 1.4 || ratio < 0.7 ? "⚠️ Please look at the screen" : "⚠️ Please keep your head straight",
              timestamp: Date.now(),
            };
            setCurrentWarning(warning);
            setViolations((prev) => [...prev, warning]);
          } else {
            setCurrentWarning(null);
          }

          requestAnimationFrame(detect);
        };

        detect();
      } catch (error) {
        console.error("Head tracking error:", error);
      }
    };

    startHeadTracking();

    return () => {
      running = false;
      if (detector && typeof detector.dispose === "function") {
        detector.dispose();
      }
      if (stream) {
        stream.getTracks().forEach((t) => t.stop());
      }
    };
  }, [enabled]);

  // Browser proctor (tab/window switching, fullscreen)
  useEffect(() => {
    if (!enabled) return;

    const onFullscreenChange = () => {
      if (!document.fullscreenElement) {
        const warning: PriorityWarning = {
          type: "fullscreen_exited",
          message: "⚠️ Fullscreen exited",
          timestamp: Date.now(),
        };
        setCurrentWarning(warning);
        setViolations((prev) => [...prev, warning]);
      }
    };

    const onVisibilityChange = () => {
      if (document.hidden) {
        const warning: PriorityWarning = {
          type: "tab_switched",
          message: "⚠️ Tab switched",
          timestamp: Date.now(),
        };
        setCurrentWarning(warning);
        setViolations((prev) => [...prev, warning]);
      }
    };

    const onBlur = () => {
      const warning: PriorityWarning = {
        type: "window_switched",
        message: "⚠️ Window switched",
        timestamp: Date.now(),
      };
      setCurrentWarning(warning);
      setViolations((prev) => [...prev, warning]);
    };

    const onCopy = (e: ClipboardEvent) => {
      e.preventDefault();
      const warning: PriorityWarning = {
        type: "copy_paste",
        message: "⚠️ Copy/Paste not allowed",
        timestamp: Date.now(),
      };
      setCurrentWarning(warning);
      setViolations((prev) => [...prev, warning]);
    };

    const onCut = (e: ClipboardEvent) => {
      e.preventDefault();
      const warning: PriorityWarning = {
        type: "copy_paste",
        message: "⚠️ Copy/Paste not allowed",
        timestamp: Date.now(),
      };
      setCurrentWarning(warning);
      setViolations((prev) => [...prev, warning]);
    };

    const onPaste = (e: ClipboardEvent) => {
      e.preventDefault();
      const warning: PriorityWarning = {
        type: "copy_paste",
        message: "⚠️ Copy/Paste not allowed",
        timestamp: Date.now(),
      };
      setCurrentWarning(warning);
      setViolations((prev) => [...prev, warning]);
    };

    document.addEventListener("fullscreenchange", onFullscreenChange);
    document.addEventListener("visibilitychange", onVisibilityChange);
    document.addEventListener("copy", onCopy);
    document.addEventListener("cut", onCut);
    document.addEventListener("paste", onPaste);
    window.addEventListener("blur", onBlur);

    return () => {
      document.removeEventListener("fullscreenchange", onFullscreenChange);
      document.removeEventListener("visibilitychange", onVisibilityChange);
      document.removeEventListener("copy", onCopy);
      document.removeEventListener("cut", onCut);
      document.removeEventListener("paste", onPaste);
      window.removeEventListener("blur", onBlur);
    };
  }, [enabled]);

  const logViolations = async (roomName: string) => {
    if (violations.length === 0) return;

    try {
      await fetch("/api/log-violations", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          room_name: roomName,
          violations: violations.map((v) => ({
            type: v.type,
            message: v.message,
            timestamp: new Date(v.timestamp).toISOString(),
          })),
        }),
      });
    } catch (error) {
      console.error("Failed to log violations:", error);
    }
  };

  return {
    videoRef,
    currentWarning,
    violations,
    logViolations,
  };
}
