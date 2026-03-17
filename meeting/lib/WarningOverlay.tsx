'use client';

import { useEffect, useState } from 'react';
import { PriorityWarning } from '@/lib/useInterviewProctor';

interface WarningOverlayProps {
  warning: PriorityWarning | null;
  violationCount: number;
}

export function WarningOverlay({ warning, violationCount }: WarningOverlayProps) {
  const [isFullscreen, setIsFullscreen] = useState(false);

  const enterFullscreen = async () => {
    try {
      await document.documentElement.requestFullscreen();
      setIsFullscreen(true);
    } catch (error) {
      console.error('Fullscreen request failed:', error);
      alert('⚠️ Fullscreen permission denied. Please enable fullscreen for this interview.');
    }
  };

  // Monitor fullscreen state changes (both button click and manual Fn+F11)
  useEffect(() => {
    const handleFullscreenChange = () => {
      setIsFullscreen(!!document.fullscreenElement);
    };

    document.addEventListener('fullscreenchange', handleFullscreenChange);
    
    return () => {
      document.removeEventListener('fullscreenchange', handleFullscreenChange);
    };
  }, []);

  return (
    <>
      {/* Fullscreen button - only visible when NOT in fullscreen */}
      {!isFullscreen && (
        <button
          onClick={enterFullscreen}
          style={{
            position: 'fixed',
            bottom: 30,
            left: '50%',
            transform: 'translateX(-50%)',
            padding: '12px 24px',
            fontSize: 16,
            fontWeight: 'bold',
            borderRadius: 8,
            border: 'none',
            background: '#4CAF50',
            color: '#fff',
            cursor: 'pointer',
            zIndex: 9998,
            boxShadow: '0 4px 12px rgba(0,0,0,0.3)',
            transition: 'background 0.3s ease',
          }}
          onMouseEnter={(e) => (e.currentTarget.style.background = '#45a049')}
          onMouseLeave={(e) => (e.currentTarget.style.background = '#4CAF50')}
        >
          📺 Enter Fullscreen
        </button>
      )}

      {/* Warning overlay - shows current violation */}
      {warning && (
        <div
          style={{
            position: 'fixed',
            top: 20,
            left: '50%',
            transform: 'translateX(-50%)',
            background: warning.type === 'head_movement' ? '#ff6b6b' : 
                       warning.type === 'copy_paste' ? '#9c27b0' : '#ff9800',
            color: '#fff',
            padding: '16px 24px',
            fontSize: 16,
            fontWeight: 'bold',
            borderRadius: 8,
            zIndex: 9999,
            boxShadow: '0 4px 12px rgba(0,0,0,0.3)',
            animation: 'pulse 0.5s ease-in-out',
          }}
        >
          {warning.message}
          {violationCount > 0 && (
            <span style={{ marginLeft: '12px', opacity: 0.8 }}>
              ({violationCount} violations)
            </span>
          )}
        </div>
      )}
    </>
  );
}
