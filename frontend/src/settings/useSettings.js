// The system settings, read once per page (Piece 28).
//
// The settings say how the app should behave — today, only whether real
// document uploads are switched on. Every signed-in screen may read them; only
// the administrator changes them, from the System administration page.
//
// The value is held in memory for as long as the page is open and is never put
// in browser storage (Rule 13). It is re-read on the next page load, so an
// admin switching it reaches everyone else the next time they move around the
// app.

import { useCallback, useEffect, useState } from "react";
import { api } from "../api/client";

export function useSettings() {
  const [settings, setSettings] = useState(null);

  const load = useCallback(() => {
    api
      .get("/settings")
      .then((res) => setSettings(res.data))
      // A failure here must never break the page that asked. Falling back to
      // "off" means the screens behave exactly as they did before Piece 28.
      .catch(() => setSettings({ real_uploads_enabled: false }));
  }, []);

  useEffect(() => { load(); }, [load]);

  return {
    // Null until the answer arrives, so a screen can wait rather than flash
    // the wrong form for a moment.
    loaded: settings !== null,
    realUploads: settings?.real_uploads_enabled === true,
    reload: load,
  };
}
