-- =============================================================================
-- FRIDA v0.5.1 - PRD-05: Technical Sheets Database Schema (CORRIGIDO)
-- =============================================================================
-- 
-- Arquivo: 08_create_technical_sheets.sql
-- Descrição: Tabelas para fichas técnicas com versionamento automático
-- Data: 2026-01-14
-- Correção: Ordem de cleanup ajustada (DROP TABLE CASCADE primeiro)
-- 
-- Tabelas:
--   1. technical_sheets - Ficha técnica atual do produto
--   2. technical_sheet_versions - Histórico de versões
--
-- Features:
--   - Versionamento automático via trigger
--   - RLS dual-mode (dev + prod)
--   - Workflow: draft → pending → approved/rejected → published
--
-- Dependências:
--   - 01_create_users_table.sql
--   - 04_create_products.sql
--
-- =============================================================================


-- =============================================================================
-- CLEANUP (Idempotente) - Ordem correta
-- =============================================================================

-- Drop tables primeiro (CASCADE remove triggers e policies automaticamente)
DROP TABLE IF EXISTS public.technical_sheet_versions CASCADE;
DROP TABLE IF EXISTS public.technical_sheets CASCADE;

-- Drop functions
DROP FUNCTION IF EXISTS public.save_sheet_version() CASCADE;
DROP FUNCTION IF EXISTS public.update_sheets_updated_at() CASCADE;


-- =============================================================================
-- 1. TABELA: technical_sheets
-- =============================================================================

CREATE TABLE public.technical_sheets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_id UUID NOT NULL UNIQUE REFERENCES public.products(id) ON DELETE CASCADE,
    version INTEGER NOT NULL DEFAULT 1,
    data JSONB NOT NULL DEFAULT '{"_version": 1, "_schema": "bag_v1"}',
    status TEXT NOT NULL DEFAULT 'draft' CHECK (
        status IN ('draft', 'pending', 'approved', 'rejected', 'published')
    ),
    rejection_comment TEXT,
    created_by UUID NOT NULL REFERENCES public.users(id),
    approved_by UUID REFERENCES public.users(id),
    approved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE public.technical_sheets IS 'Ficha técnica atual de cada produto';


-- =============================================================================
-- 2. TABELA: technical_sheet_versions
-- =============================================================================

CREATE TABLE public.technical_sheet_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sheet_id UUID NOT NULL REFERENCES public.technical_sheets(id) ON DELETE CASCADE,
    version INTEGER NOT NULL,
    data JSONB NOT NULL,
    change_summary TEXT,
    changed_by UUID NOT NULL REFERENCES public.users(id),
    changed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(sheet_id, version)
);

COMMENT ON TABLE public.technical_sheet_versions IS 'Histórico de versões das fichas técnicas';


-- =============================================================================
-- 3. ÍNDICES
-- =============================================================================

CREATE INDEX idx_sheets_product ON public.technical_sheets(product_id);
CREATE INDEX idx_sheets_status ON public.technical_sheets(status);
CREATE INDEX idx_sheets_created_by ON public.technical_sheets(created_by);
CREATE INDEX idx_versions_sheet ON public.technical_sheet_versions(sheet_id);
CREATE INDEX idx_versions_sheet_version ON public.technical_sheet_versions(sheet_id, version);


-- =============================================================================
-- 4. TRIGGER: auto-update updated_at
-- =============================================================================

CREATE OR REPLACE FUNCTION public.update_sheets_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_sheets_updated_at
    BEFORE UPDATE ON public.technical_sheets
    FOR EACH ROW
    EXECUTE FUNCTION public.update_sheets_updated_at();


-- =============================================================================
-- 5. TRIGGER: save_sheet_version (Versionamento Automático)
-- =============================================================================

CREATE OR REPLACE FUNCTION public.save_sheet_version()
RETURNS TRIGGER AS $$
BEGIN
    IF OLD.data IS DISTINCT FROM NEW.data THEN
        INSERT INTO public.technical_sheet_versions (
            sheet_id, version, data, change_summary, changed_by
        ) VALUES (
            OLD.id, OLD.version, OLD.data,
            'Versão arquivada automaticamente',
            COALESCE(auth.uid(), NEW.created_by)
        );
        
        NEW.version := OLD.version + 1;
        NEW.data := jsonb_set(NEW.data, '{_version}', to_jsonb(NEW.version));
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

CREATE TRIGGER trigger_save_sheet_version
    BEFORE UPDATE ON public.technical_sheets
    FOR EACH ROW
    EXECUTE FUNCTION public.save_sheet_version();


-- =============================================================================
-- 6. RLS POLICIES - technical_sheets
-- =============================================================================

ALTER TABLE public.technical_sheets ENABLE ROW LEVEL SECURITY;

CREATE POLICY "sheets_select_policy" ON public.technical_sheets
    FOR SELECT USING (
        auth.uid() IS NULL
        OR created_by = auth.uid()
        OR EXISTS (SELECT 1 FROM public.users WHERE id = auth.uid() AND role = 'admin')
    );

CREATE POLICY "sheets_insert_policy" ON public.technical_sheets
    FOR INSERT WITH CHECK (
        auth.uid() IS NULL OR created_by = auth.uid()
    );

CREATE POLICY "sheets_update_policy" ON public.technical_sheets
    FOR UPDATE USING (
        auth.uid() IS NULL
        OR created_by = auth.uid()
        OR EXISTS (SELECT 1 FROM public.users WHERE id = auth.uid() AND role = 'admin')
    );

CREATE POLICY "sheets_delete_policy" ON public.technical_sheets
    FOR DELETE USING (
        auth.uid() IS NULL
        OR EXISTS (SELECT 1 FROM public.users WHERE id = auth.uid() AND role = 'admin')
    );


-- =============================================================================
-- 7. RLS POLICIES - technical_sheet_versions
-- =============================================================================

ALTER TABLE public.technical_sheet_versions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "versions_select_policy" ON public.technical_sheet_versions
    FOR SELECT USING (
        auth.uid() IS NULL
        OR EXISTS (
            SELECT 1 FROM public.technical_sheets ts
            WHERE ts.id = sheet_id AND (
                ts.created_by = auth.uid()
                OR EXISTS (SELECT 1 FROM public.users WHERE id = auth.uid() AND role = 'admin')
            )
        )
    );

CREATE POLICY "versions_insert_policy" ON public.technical_sheet_versions
    FOR INSERT WITH CHECK (
        auth.uid() IS NULL OR changed_by = auth.uid()
    );

CREATE POLICY "versions_delete_policy" ON public.technical_sheet_versions
    FOR DELETE USING (
        auth.uid() IS NULL
        OR EXISTS (SELECT 1 FROM public.users WHERE id = auth.uid() AND role = 'admin')
    );


-- =============================================================================
-- 8. GRANTS
-- =============================================================================

GRANT ALL ON public.technical_sheets TO service_role;
GRANT ALL ON public.technical_sheets TO authenticated;
GRANT SELECT ON public.technical_sheets TO anon;

GRANT ALL ON public.technical_sheet_versions TO service_role;
GRANT ALL ON public.technical_sheet_versions TO authenticated;
GRANT SELECT ON public.technical_sheet_versions TO anon;


-- =============================================================================
-- 9. VALIDAÇÃO
-- =============================================================================

DO $$
BEGIN
    RAISE NOTICE '✅ PRD-05 Schema criado com sucesso!';
    RAISE NOTICE '   - technical_sheets: OK';
    RAISE NOTICE '   - technical_sheet_versions: OK';
    RAISE NOTICE '   - Triggers: 2 ativos';
    RAISE NOTICE '   - RLS Policies: 7 ativas';
END $$;
