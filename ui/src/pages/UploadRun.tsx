import { useState, useCallback } from 'react';
import { 
  Upload, FileText, CheckCircle, XCircle, Loader2, 
  ChevronRight, AlertTriangle, Eye
} from 'lucide-react';
import api from '../lib/api';

interface StepResult {
  name: string;
  status: 'pending' | 'running' | 'completed' | 'error';
  input?: Record<string, unknown>;
  output?: Record<string, unknown>;
  warnings?: string[];
  evidence_id?: string;
  trace_id?: string;
  error?: string;
}

const WORKFLOW_STEPS = [
  { id: 'intake', name: 'A. Intake & Classify', description: 'Receive document and determine type' },
  { id: 'extract', name: 'B. Extract & Normalize', description: 'OCR/PDF extraction, field extraction' },
  { id: 'validate', name: 'C. Validate', description: 'Guardrails, Pydantic validation, OPA policy' },
  { id: 'map', name: 'D. Map to Schema', description: 'Transform to ASOFT/ERP posting format' },
  { id: 'reconcile', name: 'E. Reconciliation', description: 'Cross-check with existing records' },
  { id: 'decide', name: 'F. Final Decision', description: 'Auto-approve or route for approval' },
];

export default function UploadRun() {
  const [file, setFile] = useState<File | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [jobId, setJobId] = useState<string | null>(null);
  const [steps, setSteps] = useState<StepResult[]>([]);
  const [currentStep, setCurrentStep] = useState(-1);
  const [finalStatus, setFinalStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleDrag = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files?.[0]) {
      setFile(e.dataTransfer.files[0]);
    }
  }, []);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files?.[0]) {
      setFile(e.target.files[0]);
    }
  };

  const pollJobStatus = async (id: string) => {
    const maxPolls = 60;
    let polls = 0;
    
    while (polls < maxPolls) {
      try {
        const job = await api.getJobStatus(id);
        
        // Update steps based on job data
        const newSteps: StepResult[] = WORKFLOW_STEPS.map((step, idx) => {
          if (job.status === 'completed' || job.status === 'waiting_for_approval') {
            return {
              name: step.name,
              status: 'completed',
              output: idx === 5 ? { decision: job.status } : undefined
            };
          }
          if (job.status === 'failed') {
            return {
              name: step.name,
              status: idx === 0 ? 'error' : 'pending',
              error: idx === 0 ? job.error : undefined
            };
          }
          // In progress
          const stepIndex = getStepIndexFromStatus(job.status);
          if (idx < stepIndex) {
            return { name: step.name, status: 'completed' };
          }
          if (idx === stepIndex) {
            return { name: step.name, status: 'running' };
          }
          return { name: step.name, status: 'pending' };
        });
        
        setSteps(newSteps);
        setCurrentStep(getStepIndexFromStatus(job.status));
        
        if (['completed', 'waiting_for_approval', 'failed'].includes(job.status)) {
          setFinalStatus(job.status);
          
          // Fetch detailed evidence
          try {
            const [evidence, _timeline, policy, zones] = await Promise.all([
              api.getJobEvidence(id),
              api.getJobTimeline(id),
              api.getJobPolicy(id),
              api.getJobZones(id)
            ]);
            
            // Update steps with evidence
            setSteps(prev => prev.map((s, idx) => ({
              ...s,
              evidence_id: evidence?.evidence_id,
              output: idx === 2 ? policy : idx === 4 ? zones : s.output
            })));
          } catch {
            // Evidence fetch optional
          }
          
          return;
        }
        
        await new Promise(r => setTimeout(r, 1000));
        polls++;
      } catch (err) {
        console.error('Poll error:', err);
        await new Promise(r => setTimeout(r, 2000));
        polls++;
      }
    }
    
    setError('Timeout waiting for job completion');
  };

  const getStepIndexFromStatus = (status: string): number => {
    switch (status) {
      case 'queued': return 0;
      case 'extracting': return 1;
      case 'validating': return 2;
      case 'mapping': return 3;
      case 'reconciling': return 4;
      case 'deciding': return 5;
      case 'completed':
      case 'waiting_for_approval':
      case 'failed':
        return 6;
      default:
        return 0;
    }
  };

  const handleUpload = async () => {
    if (!file) return;
    
    setUploading(true);
    setError(null);
    setSteps(WORKFLOW_STEPS.map(s => ({ name: s.name, status: 'pending' })));
    setCurrentStep(0);
    setFinalStatus(null);
    
    try {
      const response = await api.uploadDocument(file);
      setJobId(response.job_id);
      
      // Start polling
      await pollJobStatus(response.job_id);
    } catch (err) {
      setError(`Upload failed: ${err}`);
    } finally {
      setUploading(false);
    }
  };

  const reset = () => {
    setFile(null);
    setJobId(null);
    setSteps([]);
    setCurrentStep(-1);
    setFinalStatus(null);
    setError(null);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-gradient-to-r from-blue-600 to-indigo-600 rounded-xl shadow-lg p-6 text-white">
        <div className="flex items-center gap-3">
          <Upload className="w-8 h-8" />
          <div>
            <h2 className="text-xl font-bold">Upload & Run Workflow</h2>
            <p className="text-blue-100 text-sm">Upload a document and watch the processing pipeline</p>
          </div>
        </div>
      </div>

      <div className="grid lg:grid-cols-2 gap-6">
        {/* Upload Panel */}
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6">
          <h3 className="font-medium text-gray-900 mb-4">1. Select Document</h3>
          
          {!jobId ? (
            <>
              <div
                onDragEnter={handleDrag}
                onDragLeave={handleDrag}
                onDragOver={handleDrag}
                onDrop={handleDrop}
                className={`border-2 border-dashed rounded-xl p-8 text-center transition ${
                  dragActive ? 'border-blue-400 bg-blue-50' : 'border-gray-300 hover:border-gray-400'
                }`}
              >
                <Upload className="w-12 h-12 mx-auto mb-4 text-gray-400" />
                <p className="text-gray-600 mb-2">
                  Drag & drop a file here, or click to select
                </p>
                <p className="text-xs text-gray-400">
                  Supported: PDF, PNG, JPG, XLSX
                </p>
                <input
                  type="file"
                  accept=".pdf,.png,.jpg,.jpeg,.xlsx,.xls"
                  onChange={handleFileChange}
                  className="hidden"
                  id="file-upload"
                />
                <label
                  htmlFor="file-upload"
                  className="inline-block mt-4 px-4 py-2 bg-gray-100 hover:bg-gray-200 rounded-lg cursor-pointer text-sm"
                >
                  Browse Files
                </label>
              </div>
              
              {file && (
                <div className="mt-4 p-4 bg-gray-50 rounded-lg">
                  <div className="flex items-center gap-3">
                    <FileText className="w-8 h-8 text-blue-500" />
                    <div className="flex-1 min-w-0">
                      <p className="font-medium text-gray-900 truncate">{file.name}</p>
                      <p className="text-xs text-gray-500">
                        {(file.size / 1024).toFixed(1)} KB
                      </p>
                    </div>
                    <button
                      onClick={handleUpload}
                      disabled={uploading}
                      className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg flex items-center gap-2"
                    >
                      {uploading ? (
                        <Loader2 className="w-4 h-4 animate-spin" />
                      ) : (
                        <Upload className="w-4 h-4" />
                      )}
                      Upload & Process
                    </button>
                  </div>
                </div>
              )}
            </>
          ) : (
            <div className="space-y-4">
              <div className="p-4 bg-gray-50 rounded-lg">
                <div className="flex items-center gap-3">
                  <FileText className="w-8 h-8 text-blue-500" />
                  <div className="flex-1">
                    <p className="font-medium text-gray-900">{file?.name}</p>
                    <p className="text-xs text-gray-500 font-mono">Job: {jobId}</p>
                  </div>
                  {finalStatus && (
                    <span className={`px-2 py-1 rounded text-xs font-medium ${
                      finalStatus === 'completed' ? 'bg-green-100 text-green-700' :
                      finalStatus === 'waiting_for_approval' ? 'bg-yellow-100 text-yellow-700' :
                      'bg-red-100 text-red-700'
                    }`}>
                      {finalStatus}
                    </span>
                  )}
                </div>
              </div>
              
              {finalStatus && (
                <button
                  onClick={reset}
                  className="w-full py-2 bg-gray-100 hover:bg-gray-200 rounded-lg text-sm"
                >
                  Upload Another Document
                </button>
              )}
            </div>
          )}
          
          {error && (
            <div className="mt-4 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
              {error}
            </div>
          )}
        </div>

        {/* Workflow Steps */}
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6">
          <h3 className="font-medium text-gray-900 mb-4">2. Processing Pipeline</h3>
          
          <div className="space-y-3">
            {WORKFLOW_STEPS.map((step, idx) => {
              const result = steps[idx];
              const isActive = idx === currentStep;
              const isCompleted = result?.status === 'completed';
              const isError = result?.status === 'error';
              
              return (
                <div
                  key={step.id}
                  className={`p-4 rounded-lg border transition ${
                    isActive ? 'border-blue-300 bg-blue-50' :
                    isCompleted ? 'border-green-200 bg-green-50' :
                    isError ? 'border-red-200 bg-red-50' :
                    'border-gray-200'
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <div className={`w-8 h-8 rounded-full flex items-center justify-center ${
                      isActive ? 'bg-blue-500 text-white' :
                      isCompleted ? 'bg-green-500 text-white' :
                      isError ? 'bg-red-500 text-white' :
                      'bg-gray-200 text-gray-500'
                    }`}>
                      {result?.status === 'running' ? (
                        <Loader2 className="w-4 h-4 animate-spin" />
                      ) : isCompleted ? (
                        <CheckCircle className="w-4 h-4" />
                      ) : isError ? (
                        <XCircle className="w-4 h-4" />
                      ) : (
                        <span className="text-xs font-medium">{idx + 1}</span>
                      )}
                    </div>
                    <div className="flex-1">
                      <p className={`font-medium ${
                        isActive || isCompleted ? 'text-gray-900' : 'text-gray-500'
                      }`}>
                        {step.name}
                      </p>
                      <p className="text-xs text-gray-500">{step.description}</p>
                    </div>
                    {result?.output && (
                      <button className="p-1 hover:bg-white/50 rounded">
                        <Eye className="w-4 h-4 text-gray-400" />
                      </button>
                    )}
                  </div>
                  
                  {result?.error && (
                    <div className="mt-2 text-xs text-red-600 bg-red-100 p-2 rounded">
                      {result.error}
                    </div>
                  )}
                  
                  {result?.warnings && result.warnings.length > 0 && (
                    <div className="mt-2 text-xs text-yellow-600 bg-yellow-100 p-2 rounded flex items-start gap-1">
                      <AlertTriangle className="w-3 h-3 mt-0.5 flex-shrink-0" />
                      <span>{result.warnings.join(', ')}</span>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Job Details (if completed) */}
      {jobId && finalStatus && (
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6">
          <h3 className="font-medium text-gray-900 mb-4">3. Job Result</h3>
          
          <div className="grid md:grid-cols-2 gap-4">
            <a
              href={`/jobs?id=${jobId}`}
              className="p-4 bg-gray-50 hover:bg-gray-100 rounded-lg flex items-center gap-3"
            >
              <Eye className="w-5 h-5 text-gray-500" />
              <div>
                <p className="font-medium text-gray-900">View in Jobs Inspector</p>
                <p className="text-xs text-gray-500">Full details, evidence, timeline</p>
              </div>
              <ChevronRight className="w-5 h-5 text-gray-400 ml-auto" />
            </a>
            
            {finalStatus === 'waiting_for_approval' && (
              <a
                href="/approvals"
                className="p-4 bg-yellow-50 hover:bg-yellow-100 rounded-lg flex items-center gap-3"
              >
                <AlertTriangle className="w-5 h-5 text-yellow-500" />
                <div>
                  <p className="font-medium text-gray-900">Pending Approval</p>
                  <p className="text-xs text-gray-500">Review and approve in Approvals Inbox</p>
                </div>
                <ChevronRight className="w-5 h-5 text-gray-400 ml-auto" />
              </a>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
