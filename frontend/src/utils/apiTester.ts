// API Testing Utility
// This utility helps test API endpoints using the saved API key

export interface ApiTestResult {
  success: boolean;
  status: number;
  message: string;
  data?: any;
  error?: string;
}

export class ApiTester {
  private apiKey: string;
  private baseUrl: string = 'https://api.security.ait.dtu.dk';

  constructor(apiKey: string) {
    this.apiKey = apiKey;
  }

  // Test basic API connectivity
  async testConnection(): Promise<ApiTestResult> {
    try {
      console.log('🔗 Testing API connection...');
      
      const response = await fetch(`${this.baseUrl}/health`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${this.apiKey}`,
          'Content-Type': 'application/json',
        },
      });

      const data = await response.json();

      if (response.ok) {
        return {
          success: true,
          status: response.status,
          message: 'API connection successful',
          data: data,
        };
      } else {
        return {
          success: false,
          status: response.status,
          message: 'API connection failed',
          error: data.message || 'Unknown error',
        };
      }
    } catch (error: any) {
      console.error('API test failed:', error);
      return {
        success: false,
        status: 0,
        message: 'Network error',
        error: error.message,
      };
    }
  }

  // Test user profile endpoint
  async testUserProfile(): Promise<ApiTestResult> {
    try {
      console.log('👤 Testing user profile endpoint...');
      
      const response = await fetch(`${this.baseUrl}/api/user/profile`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${this.apiKey}`,
          'Content-Type': 'application/json',
        },
      });

      const data = await response.json();

      if (response.ok) {
        return {
          success: true,
          status: response.status,
          message: 'User profile retrieved successfully',
          data: data,
        };
      } else {
        return {
          success: false,
          status: response.status,
          message: 'Failed to retrieve user profile',
          error: data.message || 'Unknown error',
        };
      }
    } catch (error: any) {
      return {
        success: false,
        status: 0,
        message: 'Network error',
        error: error.message,
      };
    }
  }

  // Run a comprehensive test suite
  async runTestSuite(): Promise<ApiTestResult[]> {
    console.log('🧪 Running API test suite...');
    
    const tests = [
      { name: 'Connection Test', test: () => this.testConnection() },
      { name: 'User Profile Test', test: () => this.testUserProfile() },
    ];

    const results: ApiTestResult[] = [];

    for (const test of tests) {
      console.log(`Running ${test.name}...`);
      const result = await test.test();
      results.push(result);
      
      // Wait a bit between tests to be nice to the server
      await new Promise(resolve => setTimeout(resolve, 500));
    }

    return results;
  }
}