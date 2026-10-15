export const TEST_USER = {
  id: 1,
  name: 'Admin User',
  full_name: 'Admin User',
  email: 'admin@example.test',
  role: { id: 1, name: 'admin', description: 'Administrator' },
  is_active: true,
};

export const VIEWER_USER = {
  ...TEST_USER,
  id: 2,
  name: 'Viewer User',
  full_name: 'Viewer User',
  email: 'viewer@example.test',
  role: { id: 4, name: 'viewer', description: 'Viewer' },
};

const companies = [
  {
    id: 101,
    name: 'Acme Corporation',
    industry: 'Manufacturing',
    website: 'https://acme.example',
    phone: '+1-555-0101',
    email: 'info@acme.example',
    city: 'Austin',
    country: 'USA',
  },
];

const contacts = [
  {
    id: 201,
    first_name: 'Sarah',
    last_name: 'Johnson',
    email: 'sarah.johnson@acme.example',
    phone: '+1-555-0201',
    job_title: 'VP Sales',
    company_id: 101,
    company: companies[0],
  },
];

const leads = [
  {
    id: 301,
    title: 'Enterprise CRM Rollout',
    contact_name: 'Sarah Johnson',
    company_name: 'Acme Corporation',
    status: 'new',
    source: 'website',
    estimated_value: 42000,
  },
];

const pipelines = [
  { id: 401, name: 'Sales Pipeline', description: 'Default sales process', is_active: true },
];

const stages = [
  {
    id: 501,
    name: 'New',
    order: 1,
    probability: 10,
    total_value: 75000,
    deals: [
      {
        id: 601,
        title: 'Acme Expansion',
        value: 75000,
        company: companies[0],
        expected_close_date: '2026-10-15',
        pipeline_stage_id: 501,
      },
    ],
  },
  { id: 502, name: 'Won', order: 2, probability: 100, total_value: 0, deals: [] },
];

const tasks = [
  {
    id: 701,
    title: 'Follow up with Acme',
    description: 'Confirm procurement timeline',
    priority: 'medium',
    status: 'pending',
    due_date: '2026-10-03',
    assignee: { full_name: 'Admin User' },
  },
];

const activities = [
  {
    id: 801,
    type: 'call',
    activity_type: 'call',
    subject: 'Discovery call',
    description: 'Reviewed CRM goals',
    created_at: '2026-09-30T10:00:00Z',
  },
];

const notifications = [
  {
    id: 901,
    title: 'Export ready',
    message: 'Your pipeline export is ready.',
    notification_type: 'system',
    is_read: false,
    created_at: '2026-09-30T10:00:00Z',
  },
];

const users = [
  TEST_USER,
  {
    id: 3,
    name: 'Sales Manager',
    full_name: 'Sales Manager',
    email: 'manager@example.test',
    role: { id: 2, name: 'sales_manager' },
    is_active: true,
    created_at: '2026-09-01T00:00:00Z',
  },
];

function json(data, status = 200) {
  return {
    status,
    contentType: 'application/json',
    body: JSON.stringify(data),
  };
}

function getRoleUser(role) {
  if (role === 'viewer') return VIEWER_USER;
  return TEST_USER;
}

export async function installMockApi(page, options = {}) {
  const user = getRoleUser(options.role || 'admin');

  await page.route('**/api/v1/**', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname.replace('/api/v1', '');
    const method = request.method();

    if (path === '/auth/login' && method === 'POST') {
      const body = request.postData() || '';
      const params = new URLSearchParams(body);
      if (params.get('username') === 'admin@example.test' && params.get('password') === 'Password123!') {
        return route.fulfill(json({ access_token: 'mock-token', token_type: 'bearer' }));
      }
      return route.fulfill(json({ detail: 'Invalid credentials' }, 401));
    }

    if (path === '/auth/me') return route.fulfill(json(user));
    if (path === '/dashboard/summary') {
      return route.fulfill(json({
        total_revenue: 125000,
        active_deals_count: 7,
        conversion_rate: 33.3,
        total_leads_count: 12,
      }));
    }
    if (path === '/dashboard/sales-performance') {
      return route.fulfill(json([{ period: 'Sep 2026', deals_won: 3, revenue: 125000, win_rate: 42 }]));
    }
    if (path === '/dashboard/lead-analytics') return route.fulfill(json({ by_status: { new: 4, qualified: 2 } }));
    if (path === '/dashboard/pipeline-analytics') return route.fulfill(json({ by_stage: [{ stage_name: 'New', total_value: 75000, count: 1 }] }));
    if (path === '/dashboard/revenue-trend') return route.fulfill(json([{ period: 'Sep', revenue: 125000 }]));
    if (path === '/dashboard/activity-summary') return route.fulfill(json([{ type: 'call', count: 2 }]));
    if (path === '/dashboard/team-performance') return route.fulfill(json([{ name: 'Admin User', deals_closed: 3, revenue_generated: 125000 }]));

    if (path === '/companies' && method === 'GET') return route.fulfill(json({ items: companies, total: companies.length }));
    if (path === '/companies' && method === 'POST') return route.fulfill(json({ ...companies[0], id: 102 }, 200));
    if (path === '/companies/101') return route.fulfill(json(companies[0]));
    if (path.match(/^\/companies\/\d+$/) && method === 'PUT') return route.fulfill(json({ ...companies[0], name: 'Acme Updated' }));
    if (path.match(/^\/companies\/\d+$/) && method === 'DELETE') return route.fulfill({ status: 204, body: '' });

    if (path === '/contacts' && method === 'GET') return route.fulfill(json({ items: contacts, total: contacts.length }));
    if (path === '/contacts' && method === 'POST') return route.fulfill(json({ ...contacts[0], id: 202 }));
    if (path === '/contacts/201') return route.fulfill(json(contacts[0]));
    if (path.match(/^\/contacts\/\d+$/) && method === 'PUT') return route.fulfill(json({ ...contacts[0], first_name: 'Sara' }));
    if (path.match(/^\/contacts\/\d+$/) && method === 'DELETE') return route.fulfill({ status: 204, body: '' });

    if (path === '/leads' && method === 'GET') return route.fulfill(json({ items: leads, total: leads.length }));
    if (path === '/leads' && method === 'POST') return route.fulfill(json({ ...leads[0], id: 302 }));
    if (path === '/leads/301') return route.fulfill(json(leads[0]));
    if (path.match(/^\/leads\/\d+$/) && method === 'PUT') return route.fulfill(json({ ...leads[0], title: 'Updated Lead' }));
    if (path.match(/^\/leads\/\d+$/) && method === 'DELETE') return route.fulfill({ status: 204, body: '' });

    if (path === '/pipelines') return route.fulfill(json({ items: pipelines, total: pipelines.length }));
    if (path === '/pipelines/401/board') return route.fulfill(json({ id: 401, stages }));
    if (path === '/deals/601') return route.fulfill(json(stages[0].deals[0]));
    if (path === '/deals/601/timeline') return route.fulfill(json({ events: [{ title: 'Deal created', timestamp: '2026-09-30T10:00:00Z' }] }));
    if (path === '/deals' && method === 'POST') return route.fulfill(json({ ...stages[0].deals[0], id: 602 }));
    if (path.match(/^\/deals\/\d+$/) && method === 'PUT') return route.fulfill(json({ ...stages[0].deals[0], title: 'Updated Deal' }));
    if (path.match(/^\/deals\/\d+\/stage$/) && method === 'PATCH') return route.fulfill(json({ ...stages[0].deals[0], pipeline_stage_id: 502 }));

    if (path === '/tasks') return route.fulfill(json({ items: tasks, total: tasks.length }));
    if (path === '/tasks/701') return route.fulfill(json(tasks[0]));
    if (path.match(/^\/tasks\/\d+$/) && method === 'PUT') return route.fulfill(json({ ...tasks[0], title: 'Updated task' }));
    if (path.match(/^\/tasks\/\d+$/) && method === 'DELETE') return route.fulfill({ status: 204, body: '' });
    if (path.match(/^\/tasks\/\d+\/status$/) && method === 'PATCH') return route.fulfill(json({ ...tasks[0], status: 'completed' }));
    if (path === '/activities') return route.fulfill(json({ items: activities, total: activities.length }));

    if (path === '/notifications') return route.fulfill(json({ items: notifications, total: notifications.length }));
    if (path.match(/^\/notifications\/\d+\/read$/) && method === 'PATCH') return route.fulfill(json({ ...notifications[0], is_read: true }));
    if (path === '/notifications/read-all' && method === 'PATCH') return route.fulfill(json({ updated: 1 }));
    if (path.match(/^\/notifications\/\d+$/) && method === 'DELETE') return route.fulfill({ status: 204, body: '' });

    if (path === '/users') return route.fulfill(json({ items: users, total: users.length }));
    if (path === '/roles') {
      return route.fulfill(json({ items: [
        { id: 1, name: 'admin', description: 'Administrator' },
        { id: 4, name: 'viewer', description: 'Viewer' },
      ] }));
    }
    if (path === '/audit-logs') return route.fulfill(json({ items: [], total: 0 }));

    if (path === '/search') {
      return route.fulfill(json({
        companies,
        contacts,
        leads,
        deals: stages[0].deals,
        tasks,
      }));
    }

    if (path.startsWith('/exports/')) {
      return route.fulfill({
        status: 200,
        contentType: 'text/csv',
        body: 'id,name\n101,Acme Corporation\n',
      });
    }

    return route.fulfill(json({ detail: `Unhandled mock route: ${method} ${path}` }, 404));
  });
}

export async function authenticate(page, role = 'admin') {
  const user = getRoleUser(role);
  await page.addInitScript(({ storedUser }) => {
    window.localStorage.setItem('crm_access_token', 'mock-token');
    window.localStorage.setItem('crm_current_user', JSON.stringify(storedUser));
  }, { storedUser: user });
}

export function collectPageErrors(page) {
  const errors = [];
  page.on('pageerror', (error) => errors.push(error.message));
  return errors;
}
