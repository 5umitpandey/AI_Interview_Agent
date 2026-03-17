"use client";

import dynamic from "next/dynamic";

const EyeTestInner = dynamic(() => import("./EyeTestInner"), {
  ssr: false,
});

export default function EyeTestClient({ onViolation }: { onViolation?: (warning: string) => void }) {
  return <EyeTestInner onViolation={onViolation} />;
}
