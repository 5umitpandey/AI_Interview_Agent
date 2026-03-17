'use client';


import React, { useEffect, useState } from 'react';
import { fetchJobDescriptions } from '../lib/jd';
import API_CONFIG from "@/config/api";
// const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL ?? 'https://unicam.discretal.com/ai-led-interview';
const BACKEND_URL = API_CONFIG.BACKEND_URL;
// const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL ?? 'http://localhost:8048';

export default function HomePage() {
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [resume, setResume] = useState<File | null>(null);

  const [resumeKey, setResumeKey] = useState(0);
  const [jdList, setJdList] = useState<{ jd_id: string; title: string }[]>([]);
  const [selectedJd, setSelectedJd] = useState<string>('');

  // const [date, setDate] = useState('');
  // const [time, setTime] = useState('');

  const [loading, setLoading] = useState(false);
  const [joinUrl, setJoinUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // set default date and time on first load

  useEffect(() => {
    const now = new Date();
    // reset stale state on refresh
    setJoinUrl(null);
    setResume(null);
    setResumeKey((k) => k + 1);
    // Fetch job descriptions
    fetchJobDescriptions()
      .then((data) => {
        setJdList(data);
      })
      .catch(() => setJdList([]));
  }, []);

  async function scheduleInterview() {
    setError(null);


    if (!name || !email || !resume || !selectedJd) {
      setError('All fields are required, including Job Description');
      return;
    }

    // const scheduledDatetime = new Date(`${date}T${time}`);
    // if (scheduledDatetime < new Date()) {
    //   setError('Scheduled time cannot be in the past');
    //   return;
    // }

    setLoading(true);

    const formData = new FormData();

    formData.append('participant', name);
    formData.append('email', email);
    // formData.append('scheduled_time', scheduledDatetime.toISOString());
    formData.append('resume', resume);
    formData.append('jd_id', selectedJd);

    try {
      const resp = await fetch(`${BACKEND_URL}/api/get-token`, {
        method: 'POST',
        body: formData,
      });

      if (!resp.ok) {
        const txt = await resp.text();
        throw new Error(txt);
      }

      const data = await resp.json();
      setJoinUrl(`/ai-led-interview-app/rooms/${data.room_name}`);
    } catch (e: any) {
      setError(e.message || 'Failed to schedule interview');
    } finally {
      setLoading(false);
    }
  }

  return (
    <main style={{ minHeight: '100vh', display: 'grid', placeItems: 'center' }}>
      <div style={{ width: 420 }}>
        <h2>AI Interview Scheduler</h2>

        <input
          placeholder="Full Name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          style={{ width: '100%', marginBottom: 10 }}
        />

        <input
          placeholder="Email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          style={{ width: '100%', marginBottom: 10 }}
        />


        <input
          key={resumeKey}
          type="file"
          accept=".pdf,.docx"
          onChange={(e) => setResume(e.target.files?.[0] ?? null)}
          style={{ width: '100%', marginBottom: 10 }}
        />

        <select
          value={selectedJd}
          onChange={(e) => setSelectedJd(e.target.value)}
          style={{ width: '100%', marginBottom: 10 }}
        >
          <option value="">Select Job Description</option>
          {jdList.map((jd) => (
            <option key={jd.jd_id} value={jd.jd_id}>{jd.title}</option>
          ))}
        </select>

        {/* <input
          type="date"
          value={date}
          onChange={(e) => setDate(e.target.value)}
          style={{ width: '100%', marginBottom: 10 }}
        />

        <input
          type="time"
          value={time}
          onChange={(e) => setTime(e.target.value)}
          style={{ width: '100%', marginBottom: 10 }}
        /> */}

        <button
          onClick={scheduleInterview}
          disabled={loading}
          style={{ width: '100%', padding: 10 }}
        >
          {loading ? 'Scheduling...' : 'Schedule Interview'}
        </button>

        {error && (
          <div style={{ marginTop: 10, color: 'red' }}>
            {error}
          </div>
        )}

        {joinUrl && (
          <div style={{ marginTop: 20 }}>
            <a href={joinUrl} style={{ fontWeight: 'bold' }}>
              Join Interview
            </a>
          </div>
        )}
      </div>
    </main>
  );
}
