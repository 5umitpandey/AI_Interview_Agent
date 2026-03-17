// "use client";

// import { useEffect, useState } from "react";

// export default function BrowserProctor({ onViolation }: { onViolation?: (warning: string) => void }) {
//   const [warning, setWarning] = useState("");
//   const [isFullscreen, setIsFullscreen] = useState(false);
//   const lastViolationRef = new Map<string, number>();

//   const enterFullscreen = async () => {
//     try {
//       await document.documentElement.requestFullscreen();
//       setIsFullscreen(true);
//       setWarning("");
//     } catch {
//       setWarning("⚠️ Fullscreen permission denied");
//     }
//   };

//   useEffect(() => {
//     const onFullscreenChange = () => {
//       if (!document.fullscreenElement && isFullscreen) {
//         const warningName = "fullscreen exited";
//         setWarning("⚠️ Fullscreen exited");
//         if (onViolation) onViolation(warningName);
//         setIsFullscreen(false);
//       }
//     };

//     const onVisibilityChange = () => {
//       if (document.hidden) {
//         const warningName = "tab switched";
//         setWarning("⚠️ Tab switched");
//         if (onViolation) onViolation(warningName);
//       }
//     };

//     const onBlur = () => {
//       const warningName = "window switched";
//       setWarning("⚠️ Window switched");
//       if (onViolation) onViolation(warningName);
//     };

//     const onCopy = (e: ClipboardEvent) => {
//       e.preventDefault();
//       const warningName = "copy/paste";
//       setWarning("⚠️ Copy/Paste not allowed");
//       if (onViolation) onViolation(warningName);
//     };

//     const onCut = (e: ClipboardEvent) => {
//       e.preventDefault();
//       const warningName = "copy/paste";
//       setWarning("⚠️ Copy/Paste not allowed");
//       if (onViolation) onViolation(warningName);
//     };

//     const onPaste = (e: ClipboardEvent) => {
//       e.preventDefault();
//       const warningName = "copy/paste";
//       setWarning("⚠️ Copy/Paste not allowed");
//       if (onViolation) onViolation(warningName);
//     };

//     document.addEventListener("fullscreenchange", onFullscreenChange);
//     document.addEventListener("visibilitychange", onVisibilityChange);
//     document.addEventListener("copy", onCopy);
//     document.addEventListener("cut", onCut);
//     document.addEventListener("paste", onPaste);
//     window.addEventListener("blur", onBlur);

//     return () => {
//       document.removeEventListener("fullscreenchange", onFullscreenChange);
//       document.removeEventListener("visibilitychange", onVisibilityChange);
//       document.removeEventListener("copy", onCopy);
//       document.removeEventListener("cut", onCut);
//       document.removeEventListener("paste", onPaste);
//       window.removeEventListener("blur", onBlur);
//     };
//   }, [isFullscreen]);

//   return (
//     <>
//       {!isFullscreen && (
//         <button
//           onClick={enterFullscreen}
//           aria-label="Enter Fullscreen"
//           style={{
//             position: "fixed",
//             top: 20,
//             right: 40,
//             // left: "50%",
//             transform: "translateX(-700%)",
//             padding: "10px 18px",
//             fontSize: 15,
//             fontWeight: 700,
//             borderRadius: 8,
//             border: "none",
//             background: "#1e90ff",
//             color: "#fff",
//             cursor: "pointer",
//             zIndex: 9999,
//             boxShadow: "0 6px 18px rgba(0,0,0,0.35)",
//           }}
//         >
//           Enter Fullscreen
//         </button>
//       )}

//       {warning && (
//         <div
//           style={{
//             position: "fixed",
//             top: 20,
//             left: "50%",
//             transform: "translateX(-50%)",
//             background: "orange",
//             color: "#000",
//             padding: "14px 20px",
//             fontSize: 18,
//             fontWeight: "bold",
//             borderRadius: 8,
//             zIndex: 9999,
//           }}
//         >
//           {warning}
//         </div>
//       )}
//     </>
//   );
// }
//////////////////////////////////////////////////////////////////////////////////////////


"use client";

import { useEffect, useState } from "react";

export default function BrowserProctor({ onViolation }: { onViolation?: (warning: string) => void }) {
  const [warning, setWarning] = useState("");
  const [isFullscreen, setIsFullscreen] = useState(false);
  const lastViolationRef = new Map<string, number>();

  const enterFullscreen = async () => {
    try {
      await document.documentElement.requestFullscreen();
      setIsFullscreen(true);
      setWarning("");
    } catch {
      setWarning("⚠️ Fullscreen permission denied");
    }
  };

  useEffect(() => {
    const onFullscreenChange = () => {
      const isNowFullscreen = !!document.fullscreenElement;
      setIsFullscreen(isNowFullscreen);
      
      if (!isNowFullscreen) {
        // Exiting fullscreen
        const warningName = "fullscreen exited";
        setWarning("⚠️ Fullscreen exited");
        if (onViolation) onViolation(warningName);
      } else {
        // Entering fullscreen - clear any warnings
        setWarning("");
      }
    };

    const onVisibilityChange = () => {
      if (document.hidden) {
        const warningName = "tab switched";
        setWarning("⚠️ Tab switched");
        if (onViolation) onViolation(warningName);
      } else {
        // Tab became visible again - clear warning
        setWarning("");
      }
    };

    const onBlur = () => {
      const warningName = "window switched";
      setWarning("⚠️ Window switched");
      if (onViolation) onViolation(warningName);
    };

    const onFocus = () => {
      // Window regained focus - clear warning
      setWarning("");
    };

    const onCopy = (e: ClipboardEvent) => {
      e.preventDefault();
      const warningName = "copy/paste";
      setWarning("⚠️ Copy/Paste not allowed");
      if (onViolation) onViolation(warningName);
      // Auto-clear warning after 3 seconds
      setTimeout(() => setWarning(""), 3000);
    };

    const onCut = (e: ClipboardEvent) => {
      e.preventDefault();
      const warningName = "copy/paste";
      setWarning("⚠️ Copy/Paste not allowed");
      if (onViolation) onViolation(warningName);
      // Auto-clear warning after 3 seconds
      setTimeout(() => setWarning(""), 3000);
    };

    const onPaste = (e: ClipboardEvent) => {
      e.preventDefault();
      const warningName = "copy/paste";
      setWarning("⚠️ Copy/Paste not allowed");
      if (onViolation) onViolation(warningName);
      // Auto-clear warning after 3 seconds
      setTimeout(() => setWarning(""), 3000);
    };

    document.addEventListener("fullscreenchange", onFullscreenChange);
    document.addEventListener("visibilitychange", onVisibilityChange);
    document.addEventListener("copy", onCopy);
    document.addEventListener("cut", onCut);
    document.addEventListener("paste", onPaste);
    window.addEventListener("blur", onBlur);
    window.addEventListener("focus", onFocus);

    return () => {
      document.removeEventListener("fullscreenchange", onFullscreenChange);
      document.removeEventListener("visibilitychange", onVisibilityChange);
      document.removeEventListener("copy", onCopy);
      document.removeEventListener("cut", onCut);
      document.removeEventListener("paste", onPaste);
      window.removeEventListener("blur", onBlur);
      window.removeEventListener("focus", onFocus);
    };
  }, []);

  return (
    <>
      {!isFullscreen && (
        <button
          onClick={enterFullscreen}
          style={{
            position: "fixed",
            bottom: 30,
            left: "50%",
            transform: "translateX(-50%)",
            padding: "14px 28px",
            fontSize: 18,
            fontWeight: "bold",
            borderRadius: 8,
            border: "none",
            background: "#1e90ff",
            color: "#fff",
            cursor: "pointer",
            zIndex: 9999,
          }}
        >
          Enter Fullscreen
        </button>
      )}

      {warning && (
        <div
          style={{
            position: "fixed",
            top: 20,
            left: "50%",
            transform: "translateX(-50%)",
            background: "orange",
            color: "#000",
            padding: "14px 20px",
            fontSize: 18,
            fontWeight: "bold",
            borderRadius: 8,
            zIndex: 9999,
          }}
        >
          {warning}
        </div>
      )}
    </>
  );
}
