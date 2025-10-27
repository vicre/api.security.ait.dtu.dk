// Unfamiliar Login Page Component
// Shows login locations and diagnosed unfamiliar sign-ins over the last 3 months

import React, { useState, useEffect } from 'react';
import './UnfamiliarLoginPage.css';
import { InteractiveWorldMap } from './InteractiveWorldMap';

interface UnfamiliarLoginPageProps {
  accessToken?: string | null;
  onClose: () => void;
}

interface LoginLocation {
  id: string;
  location: string;
  city: string;
  country: string;
  ipAddress: string;
  timestamp: string;
  isFamiliar: boolean;
}



interface DiagnosedSignIn {
  id: string;
  location: string;
  riskLevel: string;
  details: string;
  action: string;
  timestamp: string;
}

const UnfamiliarLoginPage: React.FC<UnfamiliarLoginPageProps> = ({ accessToken, onClose }) => {
  const [loginLocations, setLoginLocations] = useState<LoginLocation[]>([]);
  const [diagnosedSignIns, setDiagnosedSignIns] = useState<DiagnosedSignIn[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [showMap, setShowMap] = useState(false);

  // Mock data for demonstration
  const mockLoginLocations: LoginLocation[] = [
    {
      id: '1',
      location: 'New York, United States',
      city: 'New York',
      country: 'United States',
      ipAddress: '192.168.1.100',
      timestamp: '2024-10-15T10:30:00Z',
      isFamiliar: true
    },
    {
      id: '2',
      location: 'Beijing, China',
      city: 'Beijing',
      country: 'China',
      ipAddress: '10.0.0.50',
      timestamp: '2024-10-12T08:45:00Z',
      isFamiliar: true
    },
    {
      id: '3',
      location: 'Moscow, Russia',
      city: 'Moscow',
      country: 'Russia',
      ipAddress: '172.16.0.25',
      timestamp: '2024-10-10T14:20:00Z',
      isFamiliar: false
    },
    {
      id: '4',
      location: 'Tokyo, Japan',
      city: 'Tokyo',
      country: 'Japan',
      ipAddress: '203.0.113.15',
      timestamp: '2024-10-08T16:15:00Z',
      isFamiliar: true
    }
  ];

  const mockDiagnosedSignIns: DiagnosedSignIn[] = [
    {
      id: '1',
      location: 'Lagos, Nigeria',
      riskLevel: 'High',
      details: 'Unusual login pattern detected from new geographic location with suspicious IP reputation.',
      action: 'Account temporarily locked, MFA verification required',
      timestamp: '2024-10-14T03:22:00Z'
    },
    {
      id: '2',
      location: 'São Paulo, Brazil',
      riskLevel: 'Medium',
      details: 'First-time login from this location with different browser fingerprint than usual.',
      action: 'Email notification sent, session monitored',
      timestamp: '2024-10-11T19:45:00Z'
    },
    {
      id: '3',
      location: 'Mumbai, India',
      riskLevel: 'High',
      details: 'Multiple failed login attempts followed by successful authentication from high-risk IP.',
      action: 'Account locked, password reset required',
      timestamp: '2024-10-09T11:30:00Z'
    }
  ];

  useEffect(() => {
    const fetchData = async () => {
      setIsLoading(true);
      try {
        // Simulate API call delay
        await new Promise(resolve => setTimeout(resolve, 1500));
        
        // In a real application, you would make API calls here
        // const locationsResponse = await fetch('/api/login-locations', { headers: { Authorization: `Bearer ${accessToken}` } });
        // const diagnosedResponse = await fetch('/api/diagnosed-signins', { headers: { Authorization: `Bearer ${accessToken}` } });
        
        setLoginLocations(mockLoginLocations);
        setDiagnosedSignIns(mockDiagnosedSignIns);
      } catch (error) {
        console.error('Error fetching unfamiliar login data:', error);
      } finally {
        setIsLoading(false);
      }
    };

    fetchData();
  }, [accessToken]);

  const formatDate = (dateString: string): string => {
    const date = new Date(dateString);
    return date.toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      timeZoneName: 'short'
    });
  };

  const getRiskColor = (riskLevel: string): string => {
    switch (riskLevel.toLowerCase()) {
      case 'high': return '#ef4444';
      case 'medium': return '#f59e0b';
      case 'low': return '#10b981';
      default: return '#6b7280';
    }
  };

  return (
    <div className="unfamiliar-login-overlay">
      <div className="unfamiliar-login-container">
        {/* Header */}
        <div className="unfamiliar-login-header">
          <h2>Login Activity Analysis</h2>
          <p>Past 3 months • DTU Security Monitor</p>
          <button className="close-button" onClick={onClose}>×</button>
        </div>

        {/* View Options */}
        <div className="view-options">
          <button 
            className={`view-button ${!showMap ? 'active' : ''}`}
            onClick={() => setShowMap(false)}
          >
            <span className="view-icon">📋</span>
            List View
          </button>
          <button 
            className={`view-button ${showMap ? 'active' : ''}`}
            onClick={() => setShowMap(true)}
          >
            <span className="view-icon">🗺️</span>
            World Map
          </button>
        </div>

        {/* Content Area */}
        <div className="content-area">
          {isLoading ? (
            <div className="loading-state">
              <div className="loading-spinner">🔄</div>
              <p>Loading login activity data...</p>
            </div>
          ) : (
            <>
              {!showMap ? (
                /* List View */
                <div className="list-view">
                  {/* Login Locations Section */}
                  <div className="section">
                    <div className="section-header">
                      <h3>🌍 Recent Login Locations ({loginLocations.length})</h3>
                      <p>Recent login locations detected for your account. Unfamiliar locations are highlighted for your review.</p>
                    </div>
                    
                    <div className="locations-list">
                      {loginLocations.map((location) => (
                        <div 
                          key={location.id} 
                          className={`location-item ${location.isFamiliar ? 'familiar' : 'unfamiliar'}`}
                        >
                          <div className="location-header">
                            <div className="location-info">
                              <h4>{location.location}</h4>
                              <span className="location-status">
                                {location.isFamiliar ? '✅ Familiar' : '⚠️ Unfamiliar'}
                              </span>
                            </div>
                            <span className="location-time">{formatDate(location.timestamp)}</span>
                          </div>
                          
                          <div className="location-details">
                            <div className="detail-item">
                              <span className="detail-label">IP Address:</span>
                              <span className="detail-value">{location.ipAddress}</span>
                            </div>
                            <div className="detail-item">
                              <span className="detail-label">Country:</span>
                              <span className="detail-value">{location.country}</span>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Diagnosed Threats Section */}
                  <div className="section">
                    <div className="section-header">
                      <h3>⚠️ Diagnosed Security Threats ({diagnosedSignIns.length})</h3>
                      <p>Security incidents and suspicious activities detected by our AI monitoring system.</p>
                    </div>
                    
                    <div className="diagnosed-list">
                      {diagnosedSignIns.map((signIn) => (
                        <div key={signIn.id} className="diagnosed-item">
                          <div className="diagnosed-header">
                            <div className="risk-info">
                              <h4>{signIn.location}</h4>
                              <span 
                                className="risk-badge" 
                                style={{ backgroundColor: getRiskColor(signIn.riskLevel), color: 'white' }}
                              >
                                {signIn.riskLevel} Risk
                              </span>
                            </div>
                            <span className="diagnosed-time">{formatDate(signIn.timestamp)}</span>
                          </div>
                          
                          <div className="diagnosed-details">
                            <p className="threat-description">{signIn.details}</p>
                            <div className="action-taken">
                              <span className="action-label">Action Taken:</span>
                              <span className="action-value">{signIn.action}</span>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              ) : (
                /* Interactive World Map View */
                <div className="map-view">
                  <div className="interactive-map-container">

                    
                    {/* Interactive MapLibre World Map */}
                    <InteractiveWorldMap
                      loginLocations={loginLocations.map(l => ({
                        ...l,
                        timestamp: new Date(l.timestamp)
                      }))}
                      diagnosedSignIns={diagnosedSignIns.map(s => ({
                        ...s,
                        timestamp: new Date(s.timestamp)
                      }))}
                      formatDate={(date: Date) => date.toLocaleString('en-US', {
                        month: 'short',
                        day: 'numeric',
                        year: 'numeric',
                        hour: '2-digit',
                        minute: '2-digit',
                        timeZoneName: 'short'
                      })}
                    />

                    
                  </div>
                </div>
              )}
            </>
          )}
        </div>

        {/* Footer Actions */}
        <div className="footer-actions">
          <button className="action-button secondary" onClick={onClose}>
            Close
          </button>
          <button className="action-button primary">
            Export Report
          </button>
        </div>
      </div>
    </div>
  );
};

export default UnfamiliarLoginPage;