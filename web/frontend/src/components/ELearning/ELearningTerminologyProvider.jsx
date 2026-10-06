import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { fetchELearningSettings } from "../../services/elearningSettings";
import { getELearningTerminology } from "../../config/elearningTerminology";
import { ELearningTerminologyContext } from "../../context/ELearningTerminologyContext";

export default function ELearningTerminologyProvider({ children }) {
  const [settings, setSettings] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [attempt, setAttempt] = useState(0);
  const settingsVersion = useRef(0);
  const updateSettings = useCallback((saved) => {
    settingsVersion.current += 1;
    setSettings(saved); setError(null); setLoading(false);
  }, []);
  useEffect(() => {
    let cancelled = false;
    const version = settingsVersion.current;
    fetchELearningSettings().then((data) => { if (!cancelled && version === settingsVersion.current) setSettings(data.settings || {}); })
      .catch((failure) => { if (!cancelled && version === settingsVersion.current) setError(failure); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [attempt]);
  const value = useMemo(() => ({ labels: getELearningTerminology(settings), loading, error, updateSettings,
    retry: () => { setError(null); setLoading(true); setAttempt((current) => current + 1); } }), [settings, loading, error, updateSettings]);
  return <ELearningTerminologyContext.Provider value={value}>{children}</ELearningTerminologyContext.Provider>;
}

