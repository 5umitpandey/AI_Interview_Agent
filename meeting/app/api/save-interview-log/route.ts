// import { NextRequest, NextResponse } from 'next/server';

// export async function POST(request: NextRequest) {
//   try {
//     const interviewLog = await request.json();

//     // Forward to backend FastAPI
//     const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';
//     const response = await fetch(`${backendUrl}/api/save-interview-log`, {
//       method: 'POST',
//       headers: { 'Content-Type': 'application/json' },
//       body: JSON.stringify(interviewLog),
//     });

//     if (!response.ok) {
//       throw new Error(`Backend error: ${response.statusText}`);
//     }

//     const result = await response.json();
//     return NextResponse.json(result, { status: 200 });
//   } catch (error) {
//     console.error('Error saving interview log:', error);
//     return NextResponse.json(
//       { error: 'Failed to save interview log' },
//       { status: 500 }
//     );
//   }
// }
//////////////////////////////////////////////////////////////////////////////////////////////////////////////////

import { NextRequest, NextResponse } from 'next/server';
import API_CONFIG from "@/config/api";
export async function POST(request: NextRequest) {
  try {
    const rawBody = await request.text();

    if (!rawBody) {
      return NextResponse.json(
        { error: 'Empty request body' },
        { status: 400 }
      );
    }

    const interviewLog = JSON.parse(rawBody);

    // const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'https://unicam.discretal.com/ai-led-interview';
    // const backendUrl =
    //   process.env.NEXT_PUBLIC_BACKEND_URL || 'http://backend:8048';
    const backendUrl = API_CONFIG.BACKEND_URL;
    const response = await fetch(
      `${backendUrl}/api/save-interview-log`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(interviewLog),
      }
    );

    if (!response.ok) {
      const err = await response.text();
      throw new Error(err);
    }

    const result = await response.json();
    return NextResponse.json(result, { status: 200 });

  } catch (error) {
    console.error('Error saving interview log:', error);
    return NextResponse.json(
      { error: 'Failed to save interview log' },
      { status: 500 }
    );
  }
}

