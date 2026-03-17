// // Utility to fetch job descriptions from backend
// export async function fetchJobDescriptions() {
//   const resp = await fetch(`${process.env.NEXT_PUBLIC_BACKEND_URL ?? 'http://localhost:8048'}/ai-led-interview/api/job-descriptions`);
//   if (!resp.ok) throw new Error('Failed to fetch job descriptions');
//   return resp.json();
// }
import API_CONFIG from "@/config/api";
export async function fetchJobDescriptions() {
  // const url = `${process.env.NEXT_PUBLIC_BACKEND_URL}/api/job-descriptions`;
  // const BACKEND_URL =
  //   process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8048/ai-led-interview";
  // const BACKEND_URL =
  //   process.env.NEXT_PUBLIC_BACKEND_URL ?? "https://unicam.discretal.com/ai-led-interview";
  const BACKEND_URL = API_CONFIG.BACKEND_URL;
  const url = `${BACKEND_URL}/api/job-descriptions`;

  console.log("Fetching JD from:", url);

  const resp = await fetch(url);

  if (!resp.ok) {
    throw new Error("Failed to fetch job descriptions");
  }

  const data = await resp.json();

  return data.job_descriptions;
}