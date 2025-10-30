import React, { useMemo } from 'react';
import './SwaggerDocsModal.css';

interface SwaggerDocsModalProps {
  accessToken: string | null;
  onClose: () => void;
}

const SWAGGER_BASE_URL = 'https://api.security.ait.dtu.dk/myview/swagger/';

const SwaggerDocsModal: React.FC<SwaggerDocsModalProps> = ({ accessToken, onClose }) => {
  const swaggerUrl = useMemo(() => {
    if (!accessToken) {
      return SWAGGER_BASE_URL;
    }

    const url = new URL(SWAGGER_BASE_URL);
    url.searchParams.set('access_token', accessToken);
    return url.toString();
  }, [accessToken]);

  const handleOverlayClick = (event: React.MouseEvent<HTMLDivElement>) => {
    if (event.target === event.currentTarget) {
      onClose();
    }
  };

  return (
    <div className="swagger-modal-overlay" onClick={handleOverlayClick}>
      <div className="swagger-modal-content">
        <header className="swagger-modal-header">
          <div>
            <h2>📘 Backend Swagger UI</h2>
            <p>
              Explore and test the backend API endpoints directly from the embedded Swagger UI.
            </p>
          </div>
          <div className="swagger-modal-actions">
            <a
              className="swagger-open-link"
              href={swaggerUrl}
              target="_blank"
              rel="noopener noreferrer"
            >
              Open in new tab
            </a>
            <button className="swagger-close-button" onClick={onClose} aria-label="Close swagger modal">
              ×
            </button>
          </div>
        </header>
        <div className="swagger-iframe-container">
          <iframe
            src={swaggerUrl}
            title="Backend Swagger Documentation"
            className="swagger-iframe"
            sandbox="allow-same-origin allow-scripts allow-forms allow-popups"
          />
        </div>
      </div>
    </div>
  );
};

export default SwaggerDocsModal;
