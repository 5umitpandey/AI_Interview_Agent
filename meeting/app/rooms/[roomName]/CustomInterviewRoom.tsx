import React, { useEffect, useState, useCallback, useMemo } from 'react';
import {
  useLocalParticipant,
  useRemoteParticipants,
  useRoomContext,
  VideoTrack,
  TrackReference,
  RoomAudioRenderer,
} from '@livekit/components-react';
import {
  RoomEvent,
  ConnectionState,
  Track,
} from 'livekit-client';
import styles from './CustomInterviewRoom.module.css';

export interface CustomInterviewRoomProps {
  onLeave?: () => void;
  showChat?: boolean;
}

export const CustomInterviewRoom: React.FC<CustomInterviewRoomProps> = ({
  onLeave,
  showChat = false,
}) => {
  const room = useRoomContext();
  const { cameraTrack, localParticipant, microphoneTrack } = useLocalParticipant();
  const remoteParticipants = useRemoteParticipants();
  const [micEnabled, setMicEnabled] = useState(true);
  const [cameraEnabled, setCameraEnabled] = useState(true);
  const [screenShareEnabled, setScreenShareEnabled] = useState(false);
  const [interviewStartTime, setInterviewStartTime] = useState<Date | null>(null);
  const [elapsedTime, setElapsedTime] = useState('00:00');
  const [allReady, setAllReady] = useState(false);
  
  const [connectionState, setConnectionState] = useState<ConnectionState>(
    ConnectionState.Disconnected
  );

  // Timer effect
  useEffect(() => {
    if (!interviewStartTime) return;

    const interval = setInterval(() => {
      const now = new Date();
      const elapsed = Math.floor((now.getTime() - interviewStartTime.getTime()) / 1000);
      const minutes = Math.floor(elapsed / 60);
      const seconds = elapsed % 60;
      setElapsedTime(
        `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`
      );
    }, 1000);

    return () => clearInterval(interval);
  }, [interviewStartTime]);

  // Handle room events
  useEffect(() => {
    if (!room) return;

    const onParticipantConnected = () => {
      // Participant joined, start interview
      if (!interviewStartTime) {
        setInterviewStartTime(new Date());
      }
    };

    const onConnectionStateChanged = (state: ConnectionState) => {
      setConnectionState(state);
    };

    room.on(RoomEvent.ParticipantConnected, onParticipantConnected);
    room.on(RoomEvent.ConnectionStateChanged, onConnectionStateChanged);

    return () => {
      room.off(RoomEvent.ParticipantConnected, onParticipantConnected);
      room.off(RoomEvent.ConnectionStateChanged, onConnectionStateChanged);
    };
  }, [room, interviewStartTime]);

  // Check if all participants are ready (when participant joins)
  useEffect(() => {
    if (remoteParticipants.length > 0 && localParticipant) {
      setAllReady(true);
    }
  }, [remoteParticipants.length, localParticipant]);

  const toggleMic = useCallback(async () => {
    if (localParticipant) {
      const isMicEnabled = localParticipant.isMicrophoneEnabled;
      await localParticipant.setMicrophoneEnabled(!isMicEnabled);
      setMicEnabled(!isMicEnabled);
    }
  }, [localParticipant]);

  const toggleCamera = useCallback(async () => {
    if (localParticipant) {
      const isCameraEnabled = localParticipant.isCameraEnabled;
      await localParticipant.setCameraEnabled(!isCameraEnabled);
      setCameraEnabled(!isCameraEnabled);
    }
  }, [localParticipant]);

  const toggleScreenShare = useCallback(async () => {
    // Screen share is handled by LiveKit SDK internally
    // This is a placeholder for future screen share functionality
    console.log('Screen share toggle');
  }, []);

  const handleLeave = useCallback(async () => {
    if (room) {
      await room.disconnect();
      onLeave?.();
    }
  }, [room, onLeave]);

  const participantCount = remoteParticipants.length + (localParticipant ? 1 : 0);

  // local camera track ref (for VideoTrack component)
  const localCameraTrackRef: TrackReference | undefined = useMemo(() => {
    return cameraTrack
      ? { participant: localParticipant, publication: cameraTrack, source: Track.Source.Camera }
      : undefined;
  }, [localParticipant, cameraTrack]);

  const [pinned, setPinned] = useState<TrackReference | null>(null);

  return (
    <>
    <div className={styles.container}>
      {/* Header */}
      <div className={styles.header}>
        <div className={styles.headerContent}>
          <span className={styles.logo}>🎙️</span>
          <div>
            <h1 className={styles.headerTitle}>AI Interview</h1>
            <p className={styles.headerSubtitle}>LEADER GROUP</p>
          </div>
        </div>
      </div>

      {/* Info Panel */}
      <div className={styles.infoPanel}>
        <div className={styles.infoItem}>
          <span className={styles.infoLabel}>Participants:</span>
          <span className={styles.infoValue}>{participantCount}</span>
        </div>
        <div className={styles.infoItem}>
          <span className={styles.infoLabel}>Status:</span>
          <span className={styles.infoValue}>
            🟢 {connectionState === ConnectionState.Connected ? 'Connected' : 'Connecting'}
          </span>
        </div>
        <div className={styles.timer}>
          {interviewStartTime ? elapsedTime : '00:00'}
        </div>
      </div>

      {/* Pinned (fullscreen) tile */}
      {pinned && (
        <div className={styles.pinnedContainer} onClick={() => setPinned(null)}>
          <VideoTrack trackRef={pinned} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
        </div>
      )}

      {/* Main Video Area */}
      <div className={styles.videoArea + (pinned ? ` ${styles.withPinned}` : '')}>
        <div className={styles.videoGrid}>
          {/* Local Video */}
          {localParticipant && (
            <div
              className={styles.videoContainer}
              onClick={() => localCameraTrackRef && setPinned(localCameraTrackRef)}
              role="button"
              tabIndex={0}
            >
              <div className={styles.participantVideo}>
                {localCameraTrackRef ? (
                  <VideoTrack trackRef={localCameraTrackRef} style={{ width: '100%', height: '100%', objectFit: 'cover' }} playsInline />
                ) : (
                  <div className={styles.noVideo}>
                    <span className={styles.avatarPlaceholder}>👤</span>
                    <p>You</p>
                  </div>
                )}
              </div>
              <div className={styles.participantLabel}>
                You <span className={styles.statusIndicator}></span>
                <span className={styles.muteIndicator}>{micEnabled ? '🎤' : '🔇'}</span>
              </div>
            </div>
          )}

          {/* Remote Videos */}
          {remoteParticipants.map((participant) => {
            // find camera publication (if any)
            const pub = Array.from(participant.trackPublications.values()).find(
              (p: any) => p.source === Track.Source.Camera && p.track,
            );
            const trackRef: TrackReference | undefined = pub
              ? { participant, publication: pub, source: pub.source }
              : undefined;

            return (
              <div
                key={participant.identity}
                className={styles.videoContainer}
                onClick={() => trackRef && setPinned(trackRef)}
                role="button"
                tabIndex={0}
              >
                <div className={styles.participantVideo} style={{ backgroundColor: '#000' }}>
                  {trackRef ? (
                    <VideoTrack trackRef={trackRef} style={{ width: '100%', height: '100%', objectFit: 'cover' }} playsInline />
                  ) : (
                    <div className={styles.noVideo}>
                      <span className={styles.avatarPlaceholder}>👤</span>
                      <p>{participant.name || 'Participant'}</p>
                    </div>
                  )}
                </div>
                <div className={styles.participantLabel}>
                  {participant.name || 'Participant'} <span className={styles.statusIndicator}></span>
                  <span className={styles.muteIndicator}>{(() => {
                    // Attempt to detect mute state from publication
                    try {
                      const pubs = Array.from(participant.trackPublications.values());
                      const audioPub = pubs.find((p: any) => p.source === Track.Source.Microphone);
                      // Use a safe any-cast for differing LiveKit publication shapes and
                      // normalize to a boolean to avoid TypeScript property errors.
                      const isMuted = Boolean(
                        audioPub && (((audioPub as any).muted ?? audioPub.track?.isMuted) ?? false)
                      );
                      return isMuted ? '🔇' : '🎤';
                    } catch (e) {
                      return '🎤';
                    }
                  })()}</span>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Control Bar */}
      <div className={styles.controlBar}>
        <button
          className={`${styles.controlButton} ${micEnabled ? styles.active : ''}`}
          onClick={toggleMic}
          title="Toggle Microphone (M)"
        >
          🎤
          <span className={styles.buttonLabel}>Mic</span>
        </button>

        <button
          className={`${styles.controlButton} ${cameraEnabled ? styles.active : ''}`}
          onClick={toggleCamera}
          title="Toggle Camera (C)"
        >
          📷
          <span className={styles.buttonLabel}>Camera</span>
        </button>

        <button
          className={`${styles.controlButton} ${screenShareEnabled ? styles.active : ''}`}
          onClick={toggleScreenShare}
          title="Share Screen"
        >
          🖥️
          <span className={styles.buttonLabel}>Screen</span>
        </button>

        <button
          className={`${styles.controlButton} ${styles.danger}`}
          onClick={handleLeave}
          title="End Interview (ESC)"
        >
          📞
          <span className={styles.buttonLabel}>End</span>
        </button>
      </div>
      {/* (Removed the initial 'Everyone is Ready' overlay to avoid blocking controls) */}
    </div>
    <RoomAudioRenderer />
    </>
  );
};

export default CustomInterviewRoom;
