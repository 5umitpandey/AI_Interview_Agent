import { NextRequest, NextResponse } from 'next/server';
import API_CONFIG from "@/config/api";
export async function POST(req: NextRequest) {
  try {
    const data = await req.json();
    
    // const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'https://unicam.discretal.com/ai-led-interview';
    // const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://backend:8048';
    const backendUrl = API_CONFIG.BACKEND_URL;

    const response = await fetch(`${backendUrl}/api/log-violations`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(data),
    });

    if (!response.ok) {
      console.error('Failed to log violations to backend:', await response.text());
      return NextResponse.json({ error: 'Failed to log violations' }, { status: 500 });
    }

    const result = await response.json();
    return NextResponse.json(result);
  } catch (error) {
    console.error('Error logging violations:', error);
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
  }
}
