import React, { useEffect, useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import axios from 'axios';
import { API_BASE_URL } from '../services/api';
import { Cpu, Eye, ScrollText, Save, Users, ArrowRight } from 'lucide-react';
import AdminSecurityCard from '../components/AdminSecurityCard';
import { AdminShell, PageHeader, LoadingState, ErrorState } from '../components/AdminShell';

const API_URL = API_BASE_URL;

type Config = {
  model: string;
  system_prompt: string;
  vision_model: string;
};

const AdminDashboard: React.FC = () => {
  const navigate = useNavigate();
  const token = localStorage.getItem('admin_token');
  const [config, setConfig] = useState<Config>({ model: '', system_prompt: '', vision_model: '' });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Redirect to login if not authenticated
  useEffect(() => {
    if (!token) {
      navigate('/admin');
      return;
    }
    const fetchConfig = async () => {
      try {
        const resp = await axios.get<Config>(`${API_URL}/admin/config`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        setConfig(resp.data);
      } catch (err: any) {
        setError(err?.response?.data?.detail || 'Failed to load config');
      } finally {
        setLoading(false);
      }
    };
    fetchConfig();
  }, [navigate, token]);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    const { name, value } = e.target;
    setConfig(prev => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token) return;
    try {
      const resp = await axios.put<Config>(`${API_URL}/admin/config`, config, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setConfig(resp.data);
      alert('Configuration saved successfully');
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Update failed');
    }
  };

  if (loading) return <LoadingState />;
  if (error) return <ErrorState message={error} />;

  return (
    <AdminShell>
      <PageHeader
        eyebrow="Admin Dashboard"
        title="Tutor Configuration"
        subtitle="Changes apply live to every new student message, with no restart needed."
      />

      <div className="grid lg:grid-cols-3 gap-6">
        <form onSubmit={handleSubmit} className="glass-card p-6 md:p-8 space-y-6 lg:col-span-2">
          <div>
            <label className="field-label flex items-center gap-2">
              <Cpu size={14} className="text-accent" />
              LLM Model
            </label>
            <input
              type="text"
              name="model"
              value={config.model}
              onChange={handleChange}
              className="input-premium font-mono !text-sm"
              required
            />
          </div>
          <div>
            <label className="field-label flex items-center gap-2">
              <Eye size={14} className="text-accent" />
              Vision Model
            </label>
            <input
              type="text"
              name="vision_model"
              value={config.vision_model}
              onChange={handleChange}
              placeholder="Defaults to the LLM model"
              className="input-premium font-mono !text-sm"
            />
            <p className="mt-2 text-xs text-faint">
              Used when a student attaches an image. Must be an OpenRouter model that accepts images.
            </p>
          </div>
          <div>
            <label className="field-label flex items-center gap-2">
              <ScrollText size={14} className="text-accent" />
              System Prompt
            </label>
            <textarea
              name="system_prompt"
              value={config.system_prompt}
              onChange={handleChange}
              rows={12}
              className="input-premium leading-relaxed resize-y"
              required
            />
            <p className="mt-2 text-xs text-faint">
              {config.system_prompt.length.toLocaleString()} characters
            </p>
          </div>
          <div className="flex justify-end">
            <button type="submit" className="btn-primary px-6">
              <Save size={16} />
              Save Config
            </button>
          </div>
        </form>

        <aside className="space-y-6">
          <AdminSecurityCard />
          <div className="glass-card p-6">
            <p className="text-xs font-semibold uppercase tracking-[0.14em] text-faint">Active model</p>
            <p className="mt-3 font-mono text-sm text-fg break-all">{config.model || '—'}</p>
            <p className="mt-4 text-xs font-semibold uppercase tracking-[0.14em] text-faint">Vision model</p>
            <p className="mt-2 font-mono text-sm text-fg break-all">{config.vision_model || config.model || '—'}</p>
            <span className="badge badge-live mt-4">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
              Live
            </span>
          </div>

          <Link
            to="/admin/logs"
            className="glass-card p-6 block group hover:border-line-strong transition-colors"
          >
            <span className="inline-flex items-center justify-center w-10 h-10 rounded-xl bg-accent-soft text-accent mb-4">
              <Users size={18} />
            </span>
            <p className="font-display text-xl text-fg">Student Logs</p>
            <p className="mt-1 text-sm text-muted">Browse students, sessions and full conversations.</p>
            <span className="mt-4 inline-flex items-center gap-1.5 text-sm text-accent group-hover:gap-2.5 transition-all">
              Open logs <ArrowRight size={14} />
            </span>
          </Link>
        </aside>
      </div>
    </AdminShell>
  );
};

export default AdminDashboard;
