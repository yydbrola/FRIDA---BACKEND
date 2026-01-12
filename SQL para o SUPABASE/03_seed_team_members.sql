-- ============================================================
-- Seed: Members da Equipe (Opcional)
-- ============================================================
-- 
-- INSTRUÇÕES:
-- 1. Para CADA membro, criar user no Supabase Auth (Dashboard)
-- 2. Copiar o UUID de cada um
-- 3. Substituir os placeholders abaixo
-- 4. Executar
-- 
-- ============================================================

-- Exemplo com 4 membros (ajustar conforme equipe real)
INSERT INTO public.users (id, email, name, role) VALUES
  ('[UUID-CAROL]', 'carol@empresa.com', 'Carolina Silva', 'admin'),
  ('[UUID-MARCOS]', 'marcos@empresa.com', 'Marcos Santos', 'user'),
  ('[UUID-JOAO]', 'joao@empresa.com', 'João Costa', 'user'),
  ('[UUID-MARIA]', 'maria@empresa.com', 'Maria Oliveira', 'user');

-- Verificar todos os usuários
SELECT email, name, role FROM public.users ORDER BY role DESC, name;
