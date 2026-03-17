'use client';

import React, { useEffect } from 'react';
import { useInterviewProctor } from './useInterviewProctor';

export default function ProctorPanel({ roomName }: { roomName: string }) {
  const { videoRef, currentWarning, violations, logViolations } = useInterviewProctor(true);

  useEffect(() => {
    const onBeforeUnload = () => {
      try {
        logViolations(roomName);
      } catch (e) {
        // ignore
      }
    };

    window.addEventListener('beforeunload', onBeforeUnload);
    return () => {
      window.removeEventListener('beforeunload', onBeforeUnload);
      try {
        logViolations(roomName);
      } catch (e) {}
    };
  }, [logViolations, roomName]);

  return (
    <video
      ref={videoRef}
      width={320}
      height={240}
      muted
      playsInline
      style={{ position: 'fixed', right: 10, bottom: 10, border: '2px solid #fff', transform: 'scaleX(-1)', zIndex: 9997 }}
    />
  );
}
