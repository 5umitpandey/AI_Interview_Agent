// "use client";

// import { useEffect, useRef, useState } from "react";
// import * as tf from "@tensorflow/tfjs";
// import "@tensorflow/tfjs-backend-webgl";
// import * as faceLandmarks from "@tensorflow-models/face-landmarks-detection";
// import BrowserProctor from "./BrowserProctor";

// export default function EyeTestInner({ onViolation }: { onViolation?: (warning: string) => void }) {
//   const videoRef = useRef<HTMLVideoElement | null>(null);
//   const [warning, setWarning] = useState<string>("");
//   const lastWarningRef = useRef<string>("");

//   useEffect(() => {
//     let detector: faceLandmarks.FaceLandmarksDetector;
//     let running = true;

//     const start = async () => {
//       await tf.setBackend("webgl");
//       await tf.ready();

//       detector = await faceLandmarks.createDetector(
//         faceLandmarks.SupportedModels.MediaPipeFaceMesh,
//         {
//           runtime: "tfjs",
//           refineLandmarks: true,
//         }
//       );

//       const stream = await navigator.mediaDevices.getUserMedia({
//         video: { width: 640, height: 480 },
//       });

//       const video = videoRef.current!;
//       video.srcObject = stream;
//       await video.play();

//       const detect = async () => {
//         if (!running) return;

//         const faces = await detector.estimateFaces(video);

//         if (faces.length === 0) {
//           const warningMsg = "face not detected";
//           setWarning("⚠️ Face not detected");
//           if (lastWarningRef.current !== warningMsg && onViolation) {
//             onViolation(warningMsg);
//             lastWarningRef.current = warningMsg;
//           }
//           requestAnimationFrame(detect);
//           return;
//         }

//         const keypoints = faces[0].keypoints;

//         // Stable landmark indices
//         const nose = keypoints[1];
//         const leftEye = keypoints[33];
//         const rightEye = keypoints[263];

//         if (!nose || !leftEye || !rightEye) {
//           const warningMsg = "face partially covered";
//           setWarning("⚠️ Face partially covered");
//           if (lastWarningRef.current !== warningMsg && onViolation) {
//             onViolation(warningMsg);
//             lastWarningRef.current = warningMsg;
//           }
//           requestAnimationFrame(detect);
//           return;
//         }

//         // Horizontal head turn detection (yaw)
//         const leftDist = Math.abs(nose.x - leftEye.x);
//         const rightDist = Math.abs(rightEye.x - nose.x);
//         const ratio = leftDist / rightDist;

//         // Vertical head movement (pitch)
//         const centerY = video.videoHeight / 2;
//         const verticalOffset = Math.abs(nose.y - centerY);

//         if (ratio > 1.4 || ratio < 0.7) {
//           const warningMsg = "not looking at screen";
//           setWarning("⚠️ Please look at the screen");
//           if (lastWarningRef.current !== warningMsg && onViolation) {
//             onViolation(warningMsg);
//             lastWarningRef.current = warningMsg;
//           }
//         } else if (verticalOffset > 90) {
//           const warningMsg = "head not straight";
//           setWarning("⚠️ Please keep your head straight");
//           if (lastWarningRef.current !== warningMsg && onViolation) {
//             onViolation(warningMsg);
//             lastWarningRef.current = warningMsg;
//           }
//         } else {
//           setWarning("");
//           lastWarningRef.current = "";
//         }

//         requestAnimationFrame(detect);
//       };

//       detect();
//     };

//     start();

//     return () => {
//       running = false;
//       detector?.dispose();
//     };
//   }, []);

//   return (
//     <>
//       <BrowserProctor />
//       {/* Hidden video element for face detection */}
//       <video
//         ref={videoRef}
//         width={640}
//         height={480}
//         muted
//         playsInline
//         style={{
//           display: "none",
//         }}
//       />
//       {/* Warning overlay positioned over interview */}
//       {warning && (
//         <div
//           style={{
//             position: "fixed",
//             top: 20,
//             right: 20,
//             padding: 15,
//             background: "red",
//             color: "white",
//             fontSize: 18,
//             fontWeight: "bold",
//             borderRadius: 8,
//             zIndex: 1000,
//             maxWidth: 300,
//             boxShadow: "0 4px 6px rgba(0, 0, 0, 0.3)",
//           }}
//         >
//           {warning}
//         </div>
//       )}
//     </>
//   );
// }
///////////////////////////////////////////////////////////////////////////////////////////////////////////

"use client";

import { useEffect, useRef, useState } from "react";
import * as tf from "@tensorflow/tfjs";
import "@tensorflow/tfjs-backend-webgl";
import * as faceLandmarks from "@tensorflow-models/face-landmarks-detection";
import BrowserProctor from "./BrowserProctor";

export default function EyeTestInner({ onViolation }: { onViolation?: (warning: string) => void }) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const [warning, setWarning] = useState<string>("");
  const lastWarningRef = useRef<string>("");
  const lastMultiVoiceDetectionRef = useRef<number>(0);
  const isDetectingMultipleVoicesRef = useRef<boolean>(false);
  const multiFaceFramesRef = useRef<number>(0);


  useEffect(() => {
    let detector: faceLandmarks.FaceLandmarksDetector;
    let audioContext: AudioContext | null = null;
    let running = true;

    const start = async () => {
      await tf.setBackend("webgl");
      await tf.ready();

      detector = await faceLandmarks.createDetector(
        faceLandmarks.SupportedModels.MediaPipeFaceMesh,
        {
          runtime: "tfjs",
          refineLandmarks: true,
          maxFaces: 5,
        }
      );

      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: 1280, height: 720 },
        audio: true,
      });

      const video = videoRef.current!;
      video.srcObject = stream;
      await video.play();

      // Setup audio analysis for multiple voices detection
      audioContext = new (window.AudioContext || (window as any).webkitAudioContext)();
      const analyser = audioContext.createAnalyser();
      analyser.fftSize = 2048;
      const source = audioContext.createMediaStreamSource(stream);
      source.connect(analyser);
      const dataArray = new Uint8Array(analyser.frequencyBinCount);

      const detect = async () => {
        if (!running) return;
        
        const now = Date.now();
        if (now - lastRun < 1000 / FPS) {
          requestAnimationFrame(detect);
          return;
        }
        lastRun = now;

        // Audio analysis - detect multiple voices
        analyser.getByteFrequencyData(dataArray);
        
        // Find frequency peaks (potential voice sources)
        const threshold = 50;
        let peakCount = 0;
        let lastPeakFreq = 0;
        
        for (let i = 0; i < dataArray.length; i++) {
          if (dataArray[i] > threshold) {
            // Check if this is a significant peak (separated from last peak)
            if (i - lastPeakFreq > 50) {
              peakCount++;
              lastPeakFreq = i;
            }
          }
        }
        
        // If multiple distinct frequency peaks detected (indicating multiple voices)
        if (peakCount > 2) {
          // Multiple voices ARE currently detected
          if (!isDetectingMultipleVoicesRef.current) {
            // Just started detecting multiple voices
            isDetectingMultipleVoicesRef.current = true;
            const warningMsg = "multiple voices detected";
            setWarning("⚠️ Multiple voices detected");
            lastWarningRef.current = warningMsg;
            
            // Log violation
            const now = Date.now();
            if (onViolation) {
              onViolation(warningMsg);
            }
            lastMultiVoiceDetectionRef.current = now;
          } else {
            // Still detecting multiple voices - keep warning, only re-log violation if 2+ seconds passed
            const now = Date.now();
            if (now - lastMultiVoiceDetectionRef.current > 2000) {
              if (onViolation) {
                onViolation("multiple voices detected");
              }
              lastMultiVoiceDetectionRef.current = now;
            }
          }
        } else if (isDetectingMultipleVoicesRef.current) {
          // Multiple voices were detected but NOW STOPPED - clear warning only for this
          isDetectingMultipleVoicesRef.current = false;
          if (lastWarningRef.current === "multiple voices detected") {
            setWarning("");
            lastWarningRef.current = "";
          }
        }

        const faces = await detector.estimateFaces(video);

        if (faces.length === 0) {
          const warningMsg = "face not detected";
          setWarning("⚠️ Face not detected");
          if (lastWarningRef.current !== warningMsg && onViolation) {
            onViolation(warningMsg);
            lastWarningRef.current = warningMsg;
          }
          requestAnimationFrame(detect);
          return;
        }

        if (faces.length > 1) {
          multiFaceFramesRef.current++;
                
          // trigger only after 5 continuous frames
          if (multiFaceFramesRef.current > 5) {
            const warningMsg = "multiple faces detected";
            setWarning(`⚠️ Multiple faces detected (${faces.length})`);
          
            if (lastWarningRef.current !== warningMsg && onViolation) {
              onViolation(warningMsg);
              lastWarningRef.current = warningMsg;
            }
          }
        
          requestAnimationFrame(detect);
          return;
        } else {
          // reset counter when only one face
          multiFaceFramesRef.current = 0;
        }


        const keypoints = faces[0].keypoints;

        // Stable landmark indices
        const nose = keypoints[1];
        const leftEye = keypoints[33];
        const rightEye = keypoints[263];

        if (!nose || !leftEye || !rightEye) {
          const warningMsg = "face partially covered";
          setWarning("⚠️ Face partially covered");
          if (lastWarningRef.current !== warningMsg && onViolation) {
            onViolation(warningMsg);
            lastWarningRef.current = warningMsg;
          }
          requestAnimationFrame(detect);
          return;
        }

        // Horizontal head turn detection (yaw)
        const leftDist = Math.abs(nose.x - leftEye.x);
        const rightDist = Math.abs(rightEye.x - nose.x);
        const ratio = leftDist / rightDist;

        // Vertical head movement (pitch) - detect looking up/down
        const centerY = video.videoHeight / 2;
        const noseVerticalOffset = Math.abs(nose.y - centerY);
        
        // Also check absolute position for up/down separately
        const topThreshold = video.videoHeight * 0.25; // Top 1/4 = looking up
        const bottomThreshold = video.videoHeight * 0.75; // Bottom 1/4 = looking down
        const isLookingUp = nose.y < topThreshold;
        const isLookingDown = nose.y > bottomThreshold;

        // Eye gaze detection - check if iris is at edges of eye region (looking away)
        // Iris landmarks: left iris = 468, right iris = 473
        // Eye positions: left = 33, 133 (corners), right = 263, 362 (corners)
        const leftIris = keypoints[468];
        const rightIris = keypoints[473];
        const leftEyeOuter = keypoints[33]; // left eye outer corner
        const leftEyeInner = keypoints[133]; // left eye inner corner
        const rightEyeInner = keypoints[362]; // right eye inner corner
        const rightEyeOuter = keypoints[263]; // right eye outer corner
        
        let eyeGazeWarning = "";
        if (leftIris && rightIris && leftEyeOuter && leftEyeInner && rightEyeInner && rightEyeOuter) {
          // Left eye: check if iris is too far left or right
          const leftEyeMinX = Math.min(leftEyeOuter.x, leftEyeInner.x);
          const leftEyeMaxX = Math.max(leftEyeOuter.x, leftEyeInner.x);
          const leftIrisRelative = (leftIris.x - leftEyeMinX) / (leftEyeMaxX - leftEyeMinX);
          
          // Right eye: check if iris is too far left or right
          const rightEyeMinX = Math.min(rightEyeInner.x, rightEyeOuter.x);
          const rightEyeMaxX = Math.max(rightEyeInner.x, rightEyeOuter.x);
          const rightIrisRelative = (rightIris.x - rightEyeMinX) / (rightEyeMaxX - rightEyeMinX);
          
          // Check vertical iris position too
          const leftEyeMinY = Math.min(keypoints[159]?.y || leftEyeOuter.y, keypoints[145]?.y || leftEyeOuter.y);
          const leftEyeMaxY = Math.max(keypoints[159]?.y || leftEyeOuter.y, keypoints[145]?.y || leftEyeOuter.y);
          const leftIrisVerticalRelative = (leftIris.y - leftEyeMinY) / (leftEyeMaxY - leftEyeMinY);
          
          // If iris is too far in any direction (< 0.2 or > 0.8), eyes are looking away
          const irisThresholdX = 0.25;
          const irisThresholdY = 0.3;
          
          if (leftIrisRelative < irisThresholdX || rightIrisRelative < irisThresholdX) {
            eyeGazeWarning = "eyes looking left";
          } else if (leftIrisRelative > (1 - irisThresholdX) || rightIrisRelative > (1 - irisThresholdX)) {
            eyeGazeWarning = "eyes looking right";
          } else if (leftIrisVerticalRelative < irisThresholdY) {
            eyeGazeWarning = "eyes looking up";
          } else if (leftIrisVerticalRelative > (1 - irisThresholdY)) {
            eyeGazeWarning = "eyes looking down";
          }
        }

        if (ratio > 1.4 || ratio < 0.7) {
          const warningMsg = "not looking at screen";
          setWarning("⚠️ Please look at the screen");
          if (lastWarningRef.current !== warningMsg && onViolation) {
            onViolation(warningMsg);
            lastWarningRef.current = warningMsg;
          }
        } else if (noseVerticalOffset > 70 || isLookingUp || isLookingDown) {
          const warningMsg = "head not straight";
          setWarning("⚠️ Please keep your head straight");
          if (lastWarningRef.current !== warningMsg && onViolation) {
            onViolation(warningMsg);
            lastWarningRef.current = warningMsg;
          }
        } else if (eyeGazeWarning) {
          const warningMsg = eyeGazeWarning;
          setWarning(`⚠️ Eyes ${warningMsg}`);
          if (lastWarningRef.current !== warningMsg && onViolation) {
            onViolation(warningMsg);
            lastWarningRef.current = warningMsg;
          }
        } else {
          setWarning("");
          lastWarningRef.current = "";
        }

        requestAnimationFrame(detect);
      };
      
      let lastRun = 0;
      const FPS = 8; // stable detection
      
      detect();
    };

    start();

    return () => {
      running = false;
      detector?.dispose();
      if (audioContext) {
        audioContext.close().catch(() => {});
      }
    };
  }, []);

  return (
    <>
      <BrowserProctor />
      {/* Hidden video element for face detection */}
      <video
        ref={videoRef}
        width={640}
        height={480}
        muted
        playsInline
        style={{
          display: "none",
        }}
      />
      {/* Warning overlay positioned over interview */}
      {warning && (
        <div
          style={{
            position: "fixed",
            top: 20,
            right: 20,
            padding: 15,
            background: "red",
            color: "white",
            fontSize: 18,
            fontWeight: "bold",
            borderRadius: 8,
            zIndex: 1000,
            maxWidth: 300,
            boxShadow: "0 4px 6px rgba(0, 0, 0, 0.3)",
          }}
        >
          {warning}
        </div>
      )}
    </>
  );
}

