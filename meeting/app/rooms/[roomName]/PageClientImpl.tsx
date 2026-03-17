// 'use client';

// import React from 'react';
// import { decodePassphrase } from '@/lib/client-utils';
// import { DebugMode } from '@/lib/Debug';
// import { KeyboardShortcuts } from '@/lib/KeyboardShortcuts';
// import { RecordingIndicator } from '@/lib/RecordingIndicator';
// import { SettingsMenu } from '@/lib/SettingsMenu';
// import EyeTestClient from '@/app/eye-test/EyeTestClient';
// import BrowserProctor from '@/app/eye-test/BrowserProctor';
// import CustomInterviewRoom from './CustomInterviewRoom';
// import { ConnectionDetails } from '@/lib/types';
// import {
//   formatChatMessageLinks,
//   LocalUserChoices,
//   PreJoin,
//   RoomContext,
// } from '@livekit/components-react';
// import {
//   ExternalE2EEKeyProvider,
//   RoomOptions,
//   VideoCodec,
//   VideoPresets,
//   Room,
//   DeviceUnsupportedError,
//   RoomConnectOptions,
//   RoomEvent,
//   TrackPublishDefaults,
//   VideoCaptureOptions,
// } from 'livekit-client';
// import { useRouter } from 'next/navigation';
// import { useSetupE2EE } from '@/lib/useSetupE2EE';
// import { useLowCPUOptimizer } from '@/lib/usePerfomanceOptimiser';

// const CONN_DETAILS_ENDPOINT =
//   process.env.NEXT_PUBLIC_CONN_DETAILS_ENDPOINT ?? '/api/connection-details';
// const SHOW_SETTINGS_MENU = process.env.NEXT_PUBLIC_SHOW_SETTINGS_MENU == 'true';

// export function PageClientImpl(props: {
//   roomName: string;
//   region?: string;
//   hq: boolean;
//   codec: VideoCodec;
// }) {
//   const [preJoinChoices, setPreJoinChoices] = React.useState<LocalUserChoices | undefined>(
//     undefined,
//   );
//   const preJoinDefaults = React.useMemo(() => {
//     return {
//       username: '',
//       videoEnabled: true,
//       audioEnabled: true,
//     };
//   }, []);
//   const [connectionDetails, setConnectionDetails] = React.useState<ConnectionDetails | undefined>(
//     undefined,
//   );

//   const handlePreJoinSubmit = React.useCallback(async (values: LocalUserChoices) => {
//   setPreJoinChoices(values);

//   const url = new URL(CONN_DETAILS_ENDPOINT, window.location.origin);
//   url.searchParams.set('roomName', props.roomName);
//   url.searchParams.set('participantName', values.username);

//   const resp = await fetch(url.toString());
//   if (!resp.ok) {
//     alert('Failed to join interview room');
//     return;
//   }

//   const data = await resp.json();
//   setConnectionDetails(data);
// }, [props.roomName]);

//   const handlePreJoinError = React.useCallback((e: any) => console.error(e), []);

//   return (
//     <main data-lk-theme="default" style={{ height: '100%' }}>
//       {connectionDetails === undefined || preJoinChoices === undefined ? (
//         <div style={{ display: 'grid', placeItems: 'center', height: '100%' }}>
//           <PreJoin
//             defaults={preJoinDefaults}
//             onSubmit={handlePreJoinSubmit}
//             onError={handlePreJoinError}
//           />
//         </div>
//       ) : (
//         <VideoConferenceComponent
//           connectionDetails={connectionDetails}
//           userChoices={preJoinChoices}
//           options={{ codec: props.codec, hq: props.hq }}
//         />
//       )}
//     </main>
//   );
// }

// function VideoConferenceComponent(props: {
//   userChoices: LocalUserChoices;
//   connectionDetails: ConnectionDetails;
//   options: {
//     hq: boolean;
//     codec: VideoCodec;
//   };
// }) {
//   const keyProvider = new ExternalE2EEKeyProvider();
//   const { worker, e2eePassphrase } = useSetupE2EE();
//   const e2eeEnabled = !!(e2eePassphrase && worker);

//   const [e2eeSetupComplete, setE2eeSetupComplete] = React.useState(false);
//   const interviewStartTime = React.useRef<number>(Date.now());
//   const [violations, setViolations] = React.useState<Array<{ count: number; time: string; warning: string }>>([]);
//   const violationCountRef = React.useRef<number>(0);
//   const lastViolationRef = React.useRef<{ [key: string]: number }>({});

//   // Track unique violations (not every frame)
//   const addViolation = React.useCallback((warningName: string) => {
//     const now = Date.now();
//     const elapsedMs = now - interviewStartTime.current;
//     const elapsedSec = Math.floor(elapsedMs / 1000);
//     const minutes = Math.floor(elapsedSec / 60);
//     const seconds = elapsedSec % 60;
//     const timeStr = `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;

//     // Only log if this warning hasn't been logged in the last 2 seconds
//     if (!lastViolationRef.current[warningName] || now - lastViolationRef.current[warningName] > 2000) {
//       violationCountRef.current += 1;
//       lastViolationRef.current[warningName] = now;
//       const newViolation = { count: violationCountRef.current, time: timeStr, warning: warningName };
//       setViolations((prev) => [...prev, newViolation]);
//       console.log(`[Violation ${violationCountRef.current}] ${timeStr} - ${warningName}`);
//     }
//   }, []);

//   // Eye-test components (head tracking + browser proctor) integrated as-is

//   const roomOptions = React.useMemo((): RoomOptions => {
//     let videoCodec: VideoCodec | undefined = props.options.codec ? props.options.codec : 'vp9';
//     if (e2eeEnabled && (videoCodec === 'av1' || videoCodec === 'vp9')) {
//       videoCodec = undefined;
//     }
//     const videoCaptureDefaults: VideoCaptureOptions = {
//       deviceId: props.userChoices.videoDeviceId ?? undefined,
//       resolution: props.options.hq ? VideoPresets.h2160 : VideoPresets.h720,
//     };
//     const publishDefaults: TrackPublishDefaults = {
//       dtx: false,
//       videoSimulcastLayers: props.options.hq
//         ? [VideoPresets.h1080, VideoPresets.h720]
//         : [VideoPresets.h540, VideoPresets.h216],
//       red: !e2eeEnabled,
//       videoCodec,
//     };
//     return {
//       videoCaptureDefaults: videoCaptureDefaults,
//       publishDefaults: publishDefaults,
//       audioCaptureDefaults: {
//         deviceId: props.userChoices.audioDeviceId ?? undefined,
//       },
//       adaptiveStream: true,
//       dynacast: true,
//       e2ee: keyProvider && worker && e2eeEnabled ? { keyProvider, worker } : undefined,
//       singlePeerConnection: true,
//     };
//   }, [props.userChoices, props.options.hq, props.options.codec]);

//   const room = React.useMemo(() => new Room(roomOptions), []);

//   React.useEffect(() => {
//     if (e2eeEnabled) {
//       keyProvider
//         .setKey(decodePassphrase(e2eePassphrase))
//         .then(() => {
//           room.setE2EEEnabled(true).catch((e) => {
//             if (e instanceof DeviceUnsupportedError) {
//               alert(
//                 `You're trying to join an encrypted meeting, but your browser does not support it. Please update it to the latest version and try again.`,
//               );
//               console.error(e);
//             } else {
//               throw e;
//             }
//           });
//         })
//         .then(() => setE2eeSetupComplete(true));
//     } else {
//       setE2eeSetupComplete(true);
//     }
//   }, [e2eeEnabled, room, e2eePassphrase]);

//   const connectOptions = React.useMemo((): RoomConnectOptions => {
//     return {
//       autoSubscribe: true,
//     };
//   }, []);

//   const router = useRouter();
//   const handleError = React.useCallback((error: Error) => {
//     console.error(error);
//     alert(`Encountered an unexpected error, check the console logs for details: ${error.message}`);
//   }, []);
//   const handleEncryptionError = React.useCallback((error: Error) => {
//     console.error(error);
//     alert(
//       `Encountered an unexpected encryption error, check the console logs for details: ${error.message}`,
//     );
//   }, []);

//   React.useEffect(() => {
//     const handleOnLeave = () => {
//       // Save interview violations to backend
//       const interviewEndTime = Date.now();
//       const durationMs = interviewEndTime - interviewStartTime.current;
//       const durationSec = Math.floor(durationMs / 1000);
//       const minutes = Math.floor(durationSec / 60);
//       const seconds = durationSec % 60;
//       const durationStr = `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;

//       const interviewLog = {
//         interviewId: props.connectionDetails.roomName,
//         startTime: new Date(interviewStartTime.current).toISOString(),
//         endTime: new Date(interviewEndTime).toISOString(),
//         duration: durationStr,
//         violations: violations,
//       };

//       console.log('[Interview End] Saving violations:', interviewLog);

//       // Send to backend
//       fetch('/api/save-interview-log', {
//         method: 'POST',
//         headers: { 'Content-Type': 'application/json' },
//         body: JSON.stringify(interviewLog),
//       })
//         .then((response) => response.json())
//         .then((data) => {
//           console.log('[Interview Log Saved]', data);
//           router.push('/');
//         })
//         .catch((error) => {
//           console.error('Failed to save interview log:', error);
//           router.push('/');
//         });
//     };

//     room.on(RoomEvent.Disconnected, handleOnLeave);
//     room.on(RoomEvent.EncryptionError, handleEncryptionError);
//     room.on(RoomEvent.MediaDevicesError, handleError);

//     if (e2eeSetupComplete) {
//       room
//         .connect(
//           props.connectionDetails.serverUrl,
//           props.connectionDetails.participantToken,
//           connectOptions,
//         )
//         .catch((error) => {
//           handleError(error);
//         });
//       if (props.userChoices.videoEnabled) {
//         room.localParticipant.setCameraEnabled(true).catch((error) => {
//           handleError(error);
//         });
//       }
//       if (props.userChoices.audioEnabled) {
//         room.localParticipant.setMicrophoneEnabled(true).catch((error) => {
//           handleError(error);
//         });
//       }
//     }
//     return () => {
//       room.off(RoomEvent.Disconnected, handleOnLeave);
//       room.off(RoomEvent.EncryptionError, handleEncryptionError);
//       room.off(RoomEvent.MediaDevicesError, handleError);
//     };
//   }, [e2eeSetupComplete, room, props.connectionDetails, props.userChoices, violations, router, handleEncryptionError, handleError]);

//   const lowPowerMode = useLowCPUOptimizer(room);

//   React.useEffect(() => {
//     if (lowPowerMode) {
//       console.warn('Low power mode enabled');
//     }
//   }, [lowPowerMode]);

//   const handleLeave = React.useCallback(() => {
//     room.disconnect();
//   }, [room]);

//   return (
//     <div className="lk-room-container">
//       <RoomContext.Provider value={room}>
//         <KeyboardShortcuts />
//         <CustomInterviewRoom onLeave={handleLeave} />
//         <DebugMode />
//         <RecordingIndicator />
//         <BrowserProctor onViolation={addViolation} />
//         <EyeTestClient onViolation={addViolation} />
//       </RoomContext.Provider>
//     </div>
//   );
// }

'use client';

import React from 'react';
import { decodePassphrase } from '@/lib/client-utils';
import { DebugMode } from '@/lib/Debug';
import { KeyboardShortcuts } from '@/lib/KeyboardShortcuts';
import { RecordingIndicator } from '@/lib/RecordingIndicator';
import { SettingsMenu } from '@/lib/SettingsMenu';
import EyeTestClient from '@/app/eye-test/EyeTestClient';
import BrowserProctor from '@/app/eye-test/BrowserProctor';
import CustomInterviewRoom from './CustomInterviewRoom';
import { ConnectionDetails } from '@/lib/types';
import {
  formatChatMessageLinks,
  LocalUserChoices,
  PreJoin,
  RoomContext,
} from '@livekit/components-react';
import {
  ExternalE2EEKeyProvider,
  RoomOptions,
  VideoCodec,
  VideoPresets,
  Room,
  DeviceUnsupportedError,
  RoomConnectOptions,
  RoomEvent,
  TrackPublishDefaults,
  VideoCaptureOptions,
} from 'livekit-client';
import { useRouter } from 'next/navigation';
import { useSetupE2EE } from '@/lib/useSetupE2EE';
import { useLowCPUOptimizer } from '@/lib/usePerfomanceOptimiser';

const CONN_DETAILS_ENDPOINT =
  process.env.NEXT_PUBLIC_CONN_DETAILS_ENDPOINT ?? 'ai-led-interview-app/api/connection-details';
const SHOW_SETTINGS_MENU = process.env.NEXT_PUBLIC_SHOW_SETTINGS_MENU == 'true';

export function PageClientImpl(props: {
  roomName: string;
  region?: string;
  hq: boolean;
  codec: VideoCodec;
}) {
  // ✅ ALL hooks inside the component — no hooks outside
  const [preJoinChoices, setPreJoinChoices] = React.useState<LocalUserChoices | undefined>(undefined);
  const [connectionDetails, setConnectionDetails] = React.useState<ConnectionDetails | undefined>(undefined);
  const [joinError, setJoinError] = React.useState<string | null>(null); // ✅ inside component

  const preJoinDefaults = React.useMemo(() => {
    return {
      username: '',
      videoEnabled: true,
      audioEnabled: true,
    };
  }, []);

  const handlePreJoinSubmit = React.useCallback(async (values: LocalUserChoices) => {
    setJoinError(null);

    const url = new URL(CONN_DETAILS_ENDPOINT, window.location.origin);
    url.searchParams.set('roomName', props.roomName);
    url.searchParams.set('participantName', values.username);

    const resp = await fetch(url.toString());

    if (!resp.ok) {
      // ✅ Show error from backend — do NOT set preJoinChoices so PreJoin stays visible
      const data = await resp.json().catch(() => ({ error: 'Failed to join interview room' }));
      setJoinError(data.error || data.detail || 'Failed to join interview room');
      return;
    }

    const data = await resp.json();
    setPreJoinChoices(values);
    setConnectionDetails(data);
  }, [props.roomName]);

  const handlePreJoinError = React.useCallback((e: any) => console.error(e), []);

  return (
    <main data-lk-theme="default" style={{ height: '100%' }}>
      {connectionDetails === undefined || preJoinChoices === undefined ? (
        <div style={{ display: 'grid', placeItems: 'center', height: '100%' }}>

          {/* ✅ Error banner — shows when link is used or expired */}
          {joinError && (
            <div style={{
              position: 'fixed',
              top: 30,
              left: '50%',
              transform: 'translateX(-50%)',
              background: '#e74c3c',
              color: 'white',
              padding: '16px 28px',
              borderRadius: 10,
              fontSize: 16,
              fontWeight: 'bold',
              zIndex: 9999,
              textAlign: 'center',
              maxWidth: 500,
              boxShadow: '0 4px 20px rgba(0,0,0,0.4)',
            }}>
              ⚠️ {joinError}
            </div>
          )}

          <PreJoin
            defaults={preJoinDefaults}
            onSubmit={handlePreJoinSubmit}
            onError={handlePreJoinError}
          />
        </div>
      ) : (
        <VideoConferenceComponent
          connectionDetails={connectionDetails}
          userChoices={preJoinChoices}
          options={{ codec: props.codec, hq: props.hq }}
        />
      )}
    </main>
  );
}

function VideoConferenceComponent(props: {
  userChoices: LocalUserChoices;
  connectionDetails: ConnectionDetails;
  options: {
    hq: boolean;
    codec: VideoCodec;
  };
}) {
  const keyProvider = new ExternalE2EEKeyProvider();
  const { worker, e2eePassphrase } = useSetupE2EE();
  const e2eeEnabled = !!(e2eePassphrase && worker);

  const [e2eeSetupComplete, setE2eeSetupComplete] = React.useState(false);
  const interviewStartTime = React.useRef<number>(Date.now());
  const [violations, setViolations] = React.useState<Array<{ count: number; time: string; warning: string }>>([]);
  const violationCountRef = React.useRef<number>(0);
  const lastViolationRef = React.useRef<{ [key: string]: number }>({});

  const addViolation = React.useCallback((warningName: string) => {
    const now = Date.now();
    const elapsedMs = now - interviewStartTime.current;
    const elapsedSec = Math.floor(elapsedMs / 1000);
    const minutes = Math.floor(elapsedSec / 60);
    const seconds = elapsedSec % 60;
    const timeStr = `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;

    if (!lastViolationRef.current[warningName] || now - lastViolationRef.current[warningName] > 2000) {
      violationCountRef.current += 1;
      lastViolationRef.current[warningName] = now;
      const newViolation = { count: violationCountRef.current, time: timeStr, warning: warningName };
      setViolations((prev) => [...prev, newViolation]);
      console.log(`[Violation ${violationCountRef.current}] ${timeStr} - ${warningName}`);
    }
  }, []);

  const roomOptions = React.useMemo((): RoomOptions => {
    let videoCodec: VideoCodec | undefined = props.options.codec ? props.options.codec : 'vp9';
    if (e2eeEnabled && (videoCodec === 'av1' || videoCodec === 'vp9')) {
      videoCodec = undefined;
    }
    const videoCaptureDefaults: VideoCaptureOptions = {
      deviceId: props.userChoices.videoDeviceId ?? undefined,
      resolution: props.options.hq ? VideoPresets.h2160 : VideoPresets.h720,
    };
    const publishDefaults: TrackPublishDefaults = {
      dtx: false,
      videoSimulcastLayers: props.options.hq
        ? [VideoPresets.h1080, VideoPresets.h720]
        : [VideoPresets.h540, VideoPresets.h216],
      red: !e2eeEnabled,
      videoCodec,
    };
    return {
      videoCaptureDefaults,
      publishDefaults,
      audioCaptureDefaults: {
        deviceId: props.userChoices.audioDeviceId ?? undefined,
      },
      adaptiveStream: true,
      dynacast: true,
      e2ee: keyProvider && worker && e2eeEnabled ? { keyProvider, worker } : undefined,
      singlePeerConnection: true,
    };
  }, [props.userChoices, props.options.hq, props.options.codec]);

  const room = React.useMemo(() => new Room(roomOptions), []);

  React.useEffect(() => {
    if (e2eeEnabled) {
      keyProvider
        .setKey(decodePassphrase(e2eePassphrase))
        .then(() => {
          room.setE2EEEnabled(true).catch((e) => {
            if (e instanceof DeviceUnsupportedError) {
              alert(`You're trying to join an encrypted meeting, but your browser does not support it.`);
              console.error(e);
            } else {
              throw e;
            }
          });
        })
        .then(() => setE2eeSetupComplete(true));
    } else {
      setE2eeSetupComplete(true);
    }
  }, [e2eeEnabled, room, e2eePassphrase]);

  const connectOptions = React.useMemo((): RoomConnectOptions => {
    return { autoSubscribe: true };
  }, []);

  const router = useRouter();

  const handleError = React.useCallback((error: Error) => {
    console.error(error);
    alert(`Encountered an unexpected error: ${error.message}`);
  }, []);

  const handleEncryptionError = React.useCallback((error: Error) => {
    console.error(error);
    alert(`Encountered an unexpected encryption error: ${error.message}`);
  }, []);

  React.useEffect(() => {
    const handleOnLeave = () => {
      const interviewEndTime = Date.now();
      const durationMs = interviewEndTime - interviewStartTime.current;
      const durationSec = Math.floor(durationMs / 1000);
      const minutes = Math.floor(durationSec / 60);
      const seconds = durationSec % 60;
      const durationStr = `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;

      const interviewLog = {
        interviewId: props.connectionDetails.roomName,
        startTime: new Date(interviewStartTime.current).toISOString(),
        endTime: new Date(interviewEndTime).toISOString(),
        duration: durationStr,
        violations,
      };

      console.log('[Interview End] Saving violations:', interviewLog);

      fetch('/api/save-interview-log', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(interviewLog),
      })
        .then((response) => response.json())
        .then((data) => {
          console.log('[Interview Log Saved]', data);
          router.push('/');
        })
        .catch((error) => {
          console.error('Failed to save interview log:', error);
          router.push('/');
        });
    };

    room.on(RoomEvent.Disconnected, handleOnLeave);
    room.on(RoomEvent.EncryptionError, handleEncryptionError);
    room.on(RoomEvent.MediaDevicesError, handleError);

    if (e2eeSetupComplete) {
      room
        .connect(props.connectionDetails.serverUrl, props.connectionDetails.participantToken, connectOptions)
        .catch(handleError);

      if (props.userChoices.videoEnabled) {
        room.localParticipant.setCameraEnabled(true).catch(handleError);
      }
      if (props.userChoices.audioEnabled) {
        room.localParticipant.setMicrophoneEnabled(true).catch(handleError);
      }
    }

    return () => {
      room.off(RoomEvent.Disconnected, handleOnLeave);
      room.off(RoomEvent.EncryptionError, handleEncryptionError);
      room.off(RoomEvent.MediaDevicesError, handleError);
    };
  }, [e2eeSetupComplete, room, props.connectionDetails, props.userChoices, violations, router, handleEncryptionError, handleError]);

  const lowPowerMode = useLowCPUOptimizer(room);

  React.useEffect(() => {
    if (lowPowerMode) {
      console.warn('Low power mode enabled');
    }
  }, [lowPowerMode]);

  const handleLeave = React.useCallback(() => {
    room.disconnect();
  }, [room]);

  return (
    <div className="lk-room-container">
      <RoomContext.Provider value={room}>
        <KeyboardShortcuts />
        <CustomInterviewRoom onLeave={handleLeave} />
        <DebugMode />
        <RecordingIndicator />
        <BrowserProctor onViolation={addViolation} />
        <EyeTestClient onViolation={addViolation} />
      </RoomContext.Provider>
    </div>
  );
}
