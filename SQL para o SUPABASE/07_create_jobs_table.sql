-- ============================================
-- FRIDA v0.5.1 - PRD-04: Jobs Async
-- Arquivo: 07_create_jobs_table.sql
-- Data: 2026-01-14
-- ============================================
-- 
-- Este arquivo cria a tabela 'jobs' para processamento assíncrono de imagens.
-- 
-- State Machine:
--   queued → processing → completed
--                      → failed (com retry automático)
--
-- Retry Logic:
--   - Máximo 3 tentativas por padrão
--   - Exponential backoff implementado no worker (não no SQL)
--   - Fallback: remove.bg → rembg
--
-- ============================================


-- ============================================
-- 1. DROP TABLE (se existir) - para re-execução segura
-- ============================================

DROP TABLE IF EXISTS public.jobs CASCADE;


-- ============================================
-- 2. CREATE TABLE
-- ============================================

CREATE TABLE public.jobs (
    -- Identificador único
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Relacionamento com produto
    product_id UUID NOT NULL REFERENCES public.products(id) ON DELETE CASCADE,
    
    -- State Machine
    status TEXT NOT NULL DEFAULT 'queued' CHECK (
        status IN ('queued', 'processing', 'completed', 'failed')
    ),
    
    -- Progress Tracking
    current_step TEXT DEFAULT 'uploading' CHECK (
        current_step IN (
            'uploading',      -- Fazendo upload da imagem original
            'classifying',    -- Classificando com Gemini
            'segmenting',     -- Removendo fundo (rembg/remove.bg)
            'composing',      -- Compondo fundo branco (ImageComposer)
            'validating',     -- Validando qualidade (HuskLayer)
            'saving',         -- Salvando no storage
            'done'            -- Concluído
        )
    ),
    progress INTEGER DEFAULT 0 CHECK (progress >= 0 AND progress <= 100),
    
    -- Retry Logic
    attempts INTEGER DEFAULT 0 CHECK (attempts >= 0),
    max_attempts INTEGER DEFAULT 3 CHECK (max_attempts >= 1),
    last_error TEXT,
    next_retry_at TIMESTAMPTZ,  -- Quando tentar novamente (exponential backoff)
    
    -- Provider Tracking (fallback remove.bg → rembg)
    provider TEXT CHECK (
        provider IS NULL OR provider IN ('remove.bg', 'rembg')
    ),
    
    -- Dados de entrada/saída (flexível para extensão futura)
    input_data JSONB DEFAULT '{}' NOT NULL,
    -- Estrutura esperada:
    -- {
    --   "original_filename": "bolsa.jpg",
    --   "original_path": "raw/uuid/timestamp.png",
    --   "classification": {"item": "bolsa", "estilo": "foto", "confianca": 0.95}
    -- }
    
    output_data JSONB DEFAULT '{}' NOT NULL,
    -- Estrutura esperada:
    -- {
    --   "images": {
    --     "original": {"id": "uuid", "bucket": "raw", "path": "...", "url": "..."},
    --     "segmented": {"id": "uuid", "bucket": "segmented", "path": "...", "url": "..."},
    --     "processed": {"id": "uuid", "bucket": "processed-images", "path": "...", "url": "..."}
    --   },
    --   "quality_score": 95,
    --   "quality_passed": true
    -- }
    
    -- Ownership (para RLS)
    created_by UUID NOT NULL REFERENCES public.users(id),
    
    -- Timestamps
    started_at TIMESTAMPTZ,       -- Quando mudou para 'processing'
    completed_at TIMESTAMPTZ,     -- Quando mudou para 'completed' ou 'failed'
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


-- ============================================
-- 3. COMMENTS (documentação no banco)
-- ============================================

COMMENT ON TABLE public.jobs IS 'Fila de processamento assíncrono de imagens - PRD-04';
COMMENT ON COLUMN public.jobs.status IS 'State machine: queued → processing → completed/failed';
COMMENT ON COLUMN public.jobs.current_step IS 'Etapa atual do pipeline de processamento';
COMMENT ON COLUMN public.jobs.progress IS 'Progresso de 0 a 100%';
COMMENT ON COLUMN public.jobs.provider IS 'Serviço de segmentação usado: remove.bg ou rembg';
COMMENT ON COLUMN public.jobs.next_retry_at IS 'Timestamp para próxima tentativa (exponential backoff)';


-- ============================================
-- 4. INDEXES
-- ============================================

-- Busca por status (filtro comum)
CREATE INDEX idx_jobs_status ON public.jobs(status);

-- Busca por produto
CREATE INDEX idx_jobs_product ON public.jobs(product_id);

-- Busca por criador (RLS performance)
CREATE INDEX idx_jobs_created_by ON public.jobs(created_by);

-- Fila FIFO: buscar próximo job para processar
-- Índice parcial apenas para jobs em fila
CREATE INDEX idx_jobs_queue ON public.jobs(created_at ASC)
    WHERE status = 'queued';

-- Jobs prontos para retry
CREATE INDEX idx_jobs_retry ON public.jobs(next_retry_at ASC)
    WHERE status = 'failed' AND attempts < max_attempts;


-- ============================================
-- 5. TRIGGER: Auto-update updated_at
-- ============================================

-- Função para atualizar updated_at
CREATE OR REPLACE FUNCTION update_jobs_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    
    -- Auto-preencher started_at quando muda para processing
    IF NEW.status = 'processing' AND OLD.status = 'queued' THEN
        NEW.started_at = NOW();
    END IF;
    
    -- Auto-preencher completed_at quando termina
    IF NEW.status IN ('completed', 'failed') AND OLD.status NOT IN ('completed', 'failed') THEN
        NEW.completed_at = NOW();
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger para auto-update
DROP TRIGGER IF EXISTS trigger_jobs_updated_at ON public.jobs;
CREATE TRIGGER trigger_jobs_updated_at
    BEFORE UPDATE ON public.jobs
    FOR EACH ROW
    EXECUTE FUNCTION update_jobs_updated_at();


-- ============================================
-- 6. ENABLE RLS
-- ============================================

ALTER TABLE public.jobs ENABLE ROW LEVEL SECURITY;


-- ============================================
-- 7. RLS POLICIES (Dual-Mode: dev + prod)
-- ============================================

-- DROP policies antigas (se existirem)
DROP POLICY IF EXISTS "jobs_select_policy" ON public.jobs;
DROP POLICY IF EXISTS "jobs_insert_policy" ON public.jobs;
DROP POLICY IF EXISTS "jobs_update_policy" ON public.jobs;
DROP POLICY IF EXISTS "jobs_delete_policy" ON public.jobs;

-- --------------------------------------------
-- SELECT: Dev mode OU próprios jobs OU admin
-- --------------------------------------------
CREATE POLICY "jobs_select_policy" ON public.jobs
    FOR SELECT
    USING (
        -- Dev mode: auth.uid() é NULL quando não está autenticado
        auth.uid() IS NULL
        OR
        -- Próprio usuário vê seus jobs
        created_by = auth.uid()
        OR
        -- Admin vê todos os jobs
        EXISTS (
            SELECT 1 FROM public.users
            WHERE users.id = auth.uid() AND users.role = 'admin'
        )
    );

-- --------------------------------------------
-- INSERT: Dev mode OU created_by = auth.uid()
-- --------------------------------------------
CREATE POLICY "jobs_insert_policy" ON public.jobs
    FOR INSERT
    WITH CHECK (
        -- Dev mode
        auth.uid() IS NULL
        OR
        -- Autenticado só pode criar job para si mesmo
        created_by = auth.uid()
    );

-- --------------------------------------------
-- UPDATE: Dev mode OU próprio OU admin (worker usa service_role)
-- --------------------------------------------
CREATE POLICY "jobs_update_policy" ON public.jobs
    FOR UPDATE
    USING (
        -- Dev mode
        auth.uid() IS NULL
        OR
        -- Próprio usuário pode atualizar seus jobs
        created_by = auth.uid()
        OR
        -- Admin pode atualizar qualquer job
        EXISTS (
            SELECT 1 FROM public.users
            WHERE users.id = auth.uid() AND users.role = 'admin'
        )
    )
    WITH CHECK (
        -- Mesmas regras para o novo valor
        auth.uid() IS NULL
        OR
        created_by = auth.uid()
        OR
        EXISTS (
            SELECT 1 FROM public.users
            WHERE users.id = auth.uid() AND users.role = 'admin'
        )
    );

-- --------------------------------------------
-- DELETE: Apenas admin (dev mode também permite)
-- --------------------------------------------
CREATE POLICY "jobs_delete_policy" ON public.jobs
    FOR DELETE
    USING (
        -- Dev mode
        auth.uid() IS NULL
        OR
        -- Apenas admin pode deletar jobs
        EXISTS (
            SELECT 1 FROM public.users
            WHERE users.id = auth.uid() AND users.role = 'admin'
        )
    );


-- ============================================
-- 8. GRANTS (service_role precisa de acesso explícito)
-- ============================================

-- Serviço backend (service_role) - acesso total
GRANT ALL ON public.jobs TO service_role;

-- Usuários autenticados - CRUD conforme RLS
GRANT ALL ON public.jobs TO authenticated;

-- Anon - apenas leitura (para webhooks públicos se necessário)
GRANT SELECT ON public.jobs TO anon;


-- ============================================
-- 9. VERIFICAÇÃO FINAL
-- ============================================

-- Verificar colunas criadas
SELECT 
    column_name, 
    data_type, 
    is_nullable,
    column_default
FROM information_schema.columns 
WHERE table_schema = 'public' 
AND table_name = 'jobs'
ORDER BY ordinal_position;

-- Verificar policies criadas
SELECT 
    policyname, 
    permissive,
    cmd 
FROM pg_policies 
WHERE schemaname = 'public' 
AND tablename = 'jobs';

-- Verificar índices criados
SELECT 
    indexname,
    indexdef
FROM pg_indexes 
WHERE schemaname = 'public' 
AND tablename = 'jobs';


-- ============================================
-- FIM DO ARQUIVO
-- ============================================
-- 
-- Próximos passos (implementar no Python):
-- 1. Criar JobService em app/services/job_service.py
-- 2. Criar endpoint POST /jobs para enfileirar
-- 3. Criar endpoint GET /jobs/{id} para status
-- 4. Criar worker assíncrono para processar fila
-- 5. Implementar exponential backoff no worker
-- ============================================
