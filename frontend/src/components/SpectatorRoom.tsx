import React, { useState } from "react";

interface Props {
  gameId: string | null;
  viewerCount: number;
}

export default function SpectatorRoom({ gameId, viewerCount }: Props) {
  const [copied, setCopied] = useState(false);

  if (!gameId) return null;

  const link = `${window.location.origin}/spectate/${gameId}`;

  function copyLink() {
    navigator.clipboard.writeText(link);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <div className="spectator-room">
      <button onClick={copyLink}>{copied ? "Copied!" : "Share room"}</button>
      <span className="viewer-count">{viewerCount} watching</span>
    </div>
  );
}
