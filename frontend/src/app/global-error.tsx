"use client";

import { useEffect } from "react";

/**
 * Last resort, when the root layout itself fails. It renders its own document and does not get
 * the app's stylesheet, so it uses a few inline styles.
 */
export default function GlobalError({ error, retry }: { error: unknown; retry: () => void }) {
  useEffect(() => {
    console.error(error);
  }, [error]);
  return (
    <html lang="en">
      <body style={{ fontFamily: "system-ui, sans-serif", margin: 0 }}>
        <main
          role="alert"
          style={{
            minHeight: "100vh",
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            gap: 12,
            padding: 24,
            textAlign: "center",
          }}
        >
          <h1 style={{ fontSize: 18, margin: 0 }}>Something went wrong</h1>
          <p style={{ color: "#555", margin: 0 }}>The app could not be displayed.</p>
          <button
            type="button"
            onClick={retry}
            style={{
              padding: "8px 14px",
              borderRadius: 8,
              border: "1px solid #ccc",
              cursor: "pointer",
            }}
          >
            Try again
          </button>
        </main>
      </body>
    </html>
  );
}
