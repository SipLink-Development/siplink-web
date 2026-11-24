import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { ImageResponse } from "next/og";

import { site } from "@/lib/site";

export const alt = `${site.name}: business calling, SIP trunking and business internet`;
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

// Rendered outside the page, so theme tokens cannot apply. These are the hex
// values of --primary, --foreground and --muted-foreground in app/globals.css.
const PRIMARY = "#cf164e";
const FOREGROUND = "#14171d";
const MUTED = "#5f6571";

/**
 * Default share image. WhatsApp and other chat apps crop it to a centred
 * square, so the logo sits in the middle third where every crop keeps it.
 */
export default async function OpengraphImage() {
  // PNG copy of public/siplink-logo.webp: the image renderer cannot read WebP.
  const logo = await readFile(join(process.cwd(), "assets/og/siplink-logo.png"));
  const logoSrc = `data:image/png;base64,${logo.toString("base64")}`;

  return new ImageResponse(
    <div
      style={{
        width: "100%",
        height: "100%",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        background: "#ffffff",
        backgroundImage:
          "radial-gradient(circle at 0% 0%, #fde4ea 0%, rgba(253,228,234,0) 45%), radial-gradient(circle at 100% 100%, #fde4ea 0%, rgba(253,228,234,0) 45%)",
        color: FOREGROUND,
      }}
    >
      {/* eslint-disable-next-line @next/next/no-img-element -- ImageResponse needs a plain img */}
      <img src={logoSrc} width={460} height={200} alt="" />

      <div
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          marginTop: 40,
          fontSize: 50,
          lineHeight: 1.15,
          letterSpacing: -1,
        }}
      >
        <div>Every business call.</div>
        <div style={{ color: PRIMARY }}>Connected, answered, and under control.</div>
      </div>

      <div style={{ display: "flex", alignItems: "center", marginTop: 44, fontSize: 26, color: MUTED }}>
        <div>Cloud PBX · SIP Trunking · Business Internet</div>
        <div
          style={{
            width: 8,
            height: 8,
            borderRadius: 8,
            background: PRIMARY,
            margin: "0 20px",
          }}
        />
        <div>{site.url.replace("https://", "")}</div>
      </div>
    </div>,
    size,
  );
}
