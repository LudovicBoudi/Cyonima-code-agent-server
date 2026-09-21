import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../store/auth";

export default function SsoCallback() {
  const { ssoCallback } = useAuth();
  const navigate = useNavigate();
  const [error, setError] = useState(false);

  useEffect(() => {
    ssoCallback()
      .then(() => navigate("/", { replace: true }))
      .catch(() => {
        setError(true);
        setTimeout(() => navigate("/login", { replace: true }), 1500);
      });
  }, [ssoCallback, navigate]);

  return (
    <div className="empty">
      <div>
        <h2>{error ? "Échec de la connexion SSO" : "Connexion en cours…"}</h2>
      </div>
    </div>
  );
}
