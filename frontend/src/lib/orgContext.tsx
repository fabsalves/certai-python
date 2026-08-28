import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import type { OrgListItem } from "./admin";
import { api } from "./api";
import { useAuth } from "./auth";

const STORAGE_KEY = "certai.selectedOrgId";

interface OrgState {
  orgs: OrgListItem[];
  orgsLoading: boolean;
  selectedOrgId: string | null;
  setSelectedOrgId: (id: string | null) => void;
  orgQuery: { org_id?: string };
  hasOrgLens: boolean;
}

const OrgContext = createContext<OrgState>(null!);

export function OrgProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const [orgs, setOrgs] = useState<OrgListItem[]>([]);
  const [orgsLoading, setOrgsLoading] = useState(false);
  const [selectedOrgId, setSelectedOrgIdState] = useState<string | null>(() => {
    try {
      return localStorage.getItem(STORAGE_KEY);
    } catch {
      return null;
    }
  });

  useEffect(() => {
    if (user?.role !== "superadmin") {
      setOrgs([]);
      setOrgsLoading(false);
      return;
    }
    setOrgsLoading(true);
    api
      .get<OrgListItem[]>("/admin/orgs")
      .then(({ data }) => setOrgs(data))
      .catch(() => setOrgs([]))
      .finally(() => setOrgsLoading(false));
  }, [user]);

  useEffect(() => {
    if (!orgs.length || !selectedOrgId) return;
    if (!orgs.some((org) => org.id === selectedOrgId)) {
      setSelectedOrgIdState(null);
      try {
        localStorage.removeItem(STORAGE_KEY);
      } catch {
        /* ignore */
      }
    }
  }, [orgs, selectedOrgId]);

  const setSelectedOrgId = useCallback((id: string | null) => {
    setSelectedOrgIdState(id);
    try {
      if (id) localStorage.setItem(STORAGE_KEY, id);
      else localStorage.removeItem(STORAGE_KEY);
    } catch {
      /* ignore */
    }
  }, []);

  const orgQuery = useMemo(() => {
    if (user?.role === "superadmin" && selectedOrgId) return { org_id: selectedOrgId };
    return {};
  }, [user, selectedOrgId]);

  const hasOrgLens = user?.role !== "superadmin" || Boolean(selectedOrgId);

  return (
    <OrgContext.Provider
      value={{ orgs, orgsLoading, selectedOrgId, setSelectedOrgId, orgQuery, hasOrgLens }}
    >
      {children}
    </OrgContext.Provider>
  );
}

export function useOrg() {
  return useContext(OrgContext);
}

