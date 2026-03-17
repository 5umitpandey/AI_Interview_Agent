// import { NextRequest, NextResponse } from 'next/server';
// import { AccessToken, VideoGrant } from 'livekit-server-sdk';

// const LIVEKIT_URL = process.env.LIVEKIT_URL;
// const API_KEY = process.env.LIVEKIT_API_KEY;
// const API_SECRET = process.env.LIVEKIT_API_SECRET;

// if (!LIVEKIT_URL || !API_KEY || !API_SECRET) {
//   throw new Error('LIVEKIT_URL, LIVEKIT_API_KEY, and LIVEKIT_API_SECRET must be set');
// }

// export async function GET(req: NextRequest) {
//   const roomName = req.nextUrl.searchParams.get('roomName');
//   const participantName = req.nextUrl.searchParams.get('participantName');

//   if (!roomName || !participantName) {
//     return new NextResponse('Missing parameters', { status: 400 });
//   }

//   console.log('Generating token for:', { roomName, participantName });
//   console.log('Using credentials - API_KEY:', API_KEY?.substring(0, 10), 'LIVEKIT_URL:', LIVEKIT_URL);

//   const token = new AccessToken(API_KEY, API_SECRET, {
//     identity: participantName,
//     name: participantName,
//   });

//   const grant: VideoGrant = {
//     room: roomName,
//     roomJoin: true,
//     canPublish: true,
//     canPublishData: true,
//     canSubscribe: true,
//   };

//   token.addGrant(grant);

//   const jwt = await token.toJwt();
//   console.log('Generated token:', jwt.substring(0, 50) + '...');

//   return NextResponse.json({
//     serverUrl: LIVEKIT_URL,
//     roomName,
//     participantName,
//     participantToken: jwt,
//   });
// }

import API_CONFIG from "@/config/api";


import { NextRequest, NextResponse } from 'next/server';

// const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL ?? 'https://unicam.discretal.com/ai-led-interview';
// const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL ?? 'http://backend:8048';
const BACKEND_URL = API_CONFIG.BACKEND_URL;
export async function GET(request: NextRequest) {
  const roomName = request.nextUrl.searchParams.get('roomName');
  const participantName = request.nextUrl.searchParams.get('participantName');

  if (!roomName || !participantName) {
    return NextResponse.json(
      { error: 'Missing roomName or participantName' },
      { status: 400 }
    );
  }

  try {
    // ✅ Call your Python backend /api/join-room
    // This has all checks: link expired, already completed, already used
    const resp = await fetch(
      `${BACKEND_URL}/api/join-room?room_name=${roomName}&participant=${participantName}`,
      { method: 'GET' }
    );

    if (!resp.ok) {
      // ✅ Pass exact error from backend to frontend
      const error = await resp.json().catch(() => ({ detail: 'Failed to join room' }));
      return NextResponse.json(
        { error: error.detail || 'Failed to join interview room' },
        { status: resp.status }
      );
    }

    const data = await resp.json();

    // ✅ Return in ConnectionDetails format that LiveKit frontend expects
    return NextResponse.json({
      serverUrl: data.livekit_url,
      roomName: roomName,
      participantToken: data.token,
      participantName: participantName,
    });

  } catch (e: any) {
    console.error('Backend connection error:', e);
    return NextResponse.json(
      { error: 'Could not connect to backend. Please try again.' },
      { status: 500 }
    );
  }
}
