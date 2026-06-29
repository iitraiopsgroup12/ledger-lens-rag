{{/*
Expand the name of the chart.
*/}}
{{- define "ledger-lens-rag-chart.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "ledger-lens-rag-chart.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "ledger-lens-rag-chart.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "ledger-lens-rag-chart.labels" -}}
helm.sh/chart: {{ include "ledger-lens-rag-chart.chart" . }}
{{ include "ledger-lens-rag-chart.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "ledger-lens-rag-chart.selectorLabels" -}}
app.kubernetes.io/name: {{ include "ledger-lens-rag-chart.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "ledger-lens-rag-chart.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "ledger-lens-rag-chart.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Name of the Secret holding provider API keys, either user-supplied or chart-managed.
*/}}
{{- define "ledger-lens-rag-chart.secretName" -}}
{{- default (printf "%s-secret" (include "ledger-lens-rag-chart.fullname" .)) .Values.secretEnv.existingSecret }}
{{- end }}

{{/*
Validate that the secret values required to run are actually supplied when the
chart manages the Secret. Fails the render with an actionable message instead of
silently producing empty env vars (the usual cause is a wrong --set path, e.g.
`secrets.POSTGRES_PASSWORD` or `config.POSTGRES_HOST` instead of
`secretEnv.values.POSTGRES_PASSWORD` / `env.POSTGRES_HOST`). Skipped when the
user points the chart at an existingSecret they manage themselves.
*/}}
{{- define "ledger-lens-rag-chart.validateSecrets" -}}
{{- if not .Values.secretEnv.existingSecret -}}
{{- $values := .Values.secretEnv.values | default dict -}}
{{- if not (get $values "POSTGRES_PASSWORD") -}}
{{- fail "secretEnv.values.POSTGRES_PASSWORD is required. Pass it with `--set secretEnv.values.POSTGRES_PASSWORD=<password>` (note: NOT `--set secrets.POSTGRES_PASSWORD=...`)." -}}
{{- end -}}
{{- $llmProvider := .Values.env.LLM_PROVIDER | default "openai" -}}
{{- $embProvider := .Values.env.EMBEDDING_PROVIDER | default $llmProvider -}}
{{- /* API key each provider needs in its LLM vs embedding role. Anthropic uses
       ANTHROPIC_API_KEY for the LLM but Voyage for embeddings; HuggingFace
       embeddings run locally so need no key (empty). */ -}}
{{- $llmKeys := dict "openai" "OPENAI_API_KEY" "anthropic" "ANTHROPIC_API_KEY" "google" "GOOGLE_API_KEY" "huggingface" "HUGGINGFACE_API_KEY" -}}
{{- $embKeys := dict "openai" "OPENAI_API_KEY" "anthropic" "VOYAGE_API_KEY" "google" "GOOGLE_API_KEY" "huggingface" "" -}}
{{- if not (hasKey $llmKeys $llmProvider) -}}
{{- fail (printf "env.LLM_PROVIDER=%q is not a known provider. Set one of: openai, anthropic, google, huggingface." $llmProvider) -}}
{{- end -}}
{{- if not (hasKey $embKeys $embProvider) -}}
{{- fail (printf "env.EMBEDDING_PROVIDER=%q is not a known provider. Set one of: openai, anthropic, google, huggingface (or leave empty to follow LLM_PROVIDER)." $embProvider) -}}
{{- end -}}
{{- $needed := list (get $llmKeys $llmProvider) -}}
{{- $embKey := get $embKeys $embProvider -}}
{{- if $embKey -}}{{- $needed = append $needed $embKey -}}{{- end -}}
{{- range $needed | uniq -}}
{{- if not (get $values .) -}}
{{- fail (printf "secretEnv.values.%s is required for LLM_PROVIDER=%s / EMBEDDING_PROVIDER=%s. Pass it with `--set secretEnv.values.%s=<key>`." . $llmProvider $embProvider .) -}}
{{- end -}}
{{- end -}}
{{- end -}}
{{- end -}}

{{/*
Name of the PVC backing the FAISS index, either user-supplied or chart-managed.
*/}}
{{- define "ledger-lens-rag-chart.pvcName" -}}
{{- default (printf "%s-data" (include "ledger-lens-rag-chart.fullname" .)) .Values.persistence.existingClaim }}
{{- end }}

{{/*
Name of the PVC backing the KPI document storage, either user-supplied or chart-managed.
*/}}
{{- define "ledger-lens-rag-chart.storagePvcName" -}}
{{- default (printf "%s-storage" (include "ledger-lens-rag-chart.fullname" .)) .Values.storagePersistence.existingClaim }}
{{- end }}
