# -*- coding: utf-8 -*-
"""
Versão comentada linha a linha de movns.py.
Objetivo: Explicar cada instrução/ação executada no código MOVNS para facilitar estudo e manutenção.
Observação: Lógica mantida idêntica ao arquivo original (movns.py). Apenas foram adicionados comentários.
"""

import random  # Módulo para geração de números aleatórios e escolhas randômicas
import time    # Módulo para medir tempo de execução (usado em iterações)
import copy    # Módulo para realizar cópias profundas (deepcopy) de objetos complexos
from typing import List, Dict, Tuple, Set, Optional, Any  # Tipagem estática opcional para clareza
from models import Solution, Hotel, DailyRoute, Attraction, TransportMode  # Importa classes de domínio

class MOVNS:
    """
    Implementação de MOVNS (Multi-Objective Variable Neighborhood Search) para planejamento turístico.
    Objetivo: Encontrar um conjunto Pareto-ótimo de soluções balanceando múltiplos critérios.

    Objetivos considerados:
    F1: Maximizar número de atrações visitadas
    F2: Maximizar qualidade total (soma das notas)
    F3: Minimizar tempo total
    F4: Minimizar custo total

    Diferença principal de NSGA-II: Uso explícito de vizinhanças variáveis em sequência.
    """
    
    def __init__(self, constructor, solution_count=100, archive_max=30):  # Inicializa instância do algoritmo
        self.constructor = constructor  # Guardamos o gerador de soluções iniciais
        self.pareto_set: List[Solution] = []  # Arquivo (frente) Pareto corrente
        self.solution_count = solution_count  # Tamanho da população inicial desejada
        self.archive_max = archive_max  # Tamanho máximo do arquivo/arquivo Pareto (truncado por crowding)
        
        self.neighborhoods = [  # Lista ordenada de funções de vizinhança (exploração incremental k)
            self._neighborhood_swap_within_day,        # Troca duas atrações no mesmo dia
            self._neighborhood_move_between_days,      # Move atração de um dia para o outro
            self._neighborhood_replace_attraction,     # Substitui uma atração por outra não usada
            self._neighborhood_add_attraction,         # Adiciona nova atração em alguma posição
            self._neighborhood_remove_attraction,      # Remove uma atração existente
            self._neighborhood_change_hotel,           # Troca o hotel
            self._neighborhood_change_transport        # Altera modo de transporte em um segmento
        ]
        
        self.iteration_metrics: List[Dict[str, Any]] = []  # Histórico de métricas por iteração
        self.best_solutions: Dict[str, Solution] = {}      # Melhores soluções isoladas por objetivo
        
        self._mode_validity_cache: Dict[Tuple[str, str], List[TransportMode]] = {}  # Cache de modos válidos
    
    def initialize_population(self) -> List[Solution]:  # Gera população inicial e monta frente inicial
        print(f"Generating initial population of size {self.solution_count}...")  # Log informativo
        
        initial_solutions = self.constructor.generate_initial_population(self.solution_count)  # Cria soluções
        
        if initial_solutions:  # Se houver pelo menos uma solução
            self._calculate_initial_metrics(initial_solutions)  # Calcula métricas agregadas iniciais
        
        for solution in initial_solutions:  # Itera sobre todas as soluções iniciais
            self._add_to_pareto_set(solution)  # Tenta inserir na frente Pareto
        
        print(f"Initial Pareto set size: {len(self.pareto_set)}")  # Tamanho após filtragem de dominância
        return self.pareto_set  # Retorna frente inicial
    
    def run(self, max_iterations=100, max_no_improvement=20) -> List[Solution]:  # Loop principal MOVNS
        if not self.pareto_set:  # Garante inicialização anterior
            raise ValueError("Pareto set not initialized. Call initialize_population first.")  # Erro se faltou init
        
        print(f"Starting MOVNS optimization ({max_iterations} max iterations)...")  # Log início
        
        iteration = 0  # Contador de iterações globais
        no_improvement = 0  # Contador de iterações sem melhoria
        
        pareto_sizes = [len(self.pareto_set)]  # Histórico de tamanhos da frente (não usado externamente diretamente)
        
        while iteration < max_iterations and no_improvement < max_no_improvement:  # Critérios de parada
            start_time = time.time()  # Marca tempo inicial da iteração
            current_size = len(self.pareto_set)  # Tamanho atual do arquivo antes de explorar vizinhanças
            improved = False  # Flag de melhoria
            
            for i, solution in enumerate(self.pareto_set[:]):  # Copia superficial para iterar sobre estado estável
                k = 0  # Índice de vizinhança inicial
                
                while k < len(self.neighborhoods):  # Percorre vizinhanças progressivamente
                    new_solution = self._shake(solution, k)  # Aplica perturbação (gera solução vizinha)
                    
                    if new_solution:  # Se houve modificação válida
                        improved_solution = self._multi_objective_local_search(new_solution)  # Descida local ponderada
                        
                        if self._add_to_pareto_set(improved_solution):  # Tenta inserir no arquivo Pareto
                            improved = True  # Marcamos melhoria global
                            k = 0  # Reinicia sequência de vizinhanças (intensificação)
                        else:
                            k += 1  # Avança para próxima vizinhança
                    else:
                        k += 1  # Sem vizinho válido -> testa próxima vizinhança
            
            if improved or len(self.pareto_set) > current_size:  # Se houve melhoria (arquivo cresceu ou substituições)
                no_improvement = 0  # Reseta contador de estagnação
            else:
                no_improvement += 1  # Incrementa estagnação
            
            iteration += 1  # Incrementa iteração
            elapsed = time.time() - start_time  # Tempo gasto nesta iteração
            pareto_sizes.append(len(self.pareto_set))  # Registra evolução do tamanho
            
            metrics = self._calculate_iteration_metrics(iteration, elapsed)  # Coleta métricas atuais
            self.iteration_metrics.append(metrics)  # Armazena
            
            print(f"Iteration {iteration}/{max_iterations} | "  # Log detalhado de progresso
                  f"Pareto set size: {len(self.pareto_set)} | "
                  f"No improvement: {no_improvement}/{max_no_improvement} | "
                  f"Time: {elapsed:.2f}s")
        
        if iteration >= max_iterations:  # Motivo de parada 1
            print(f"Stopping: maximum iterations ({max_iterations}) reached")  # Log
        else:  # Motivo de parada 2 (sem melhoria)
            print(f"Stopping: {max_no_improvement} iterations without improvement")  # Log
        
        print(f"Final Pareto set size: {len(self.pareto_set)}")  # Tamanho final
        
        return self.pareto_set  # Retorna frente final
    
    def _shake(self, solution: Solution, k: int) -> Optional[Solution]:  # Aplica vizinhança k em uma cópia
        perturbed = copy.deepcopy(solution)  # Cópia independente do objeto original
        
        if k < len(self.neighborhoods):  # Verifica se k é índice válido
            return self.neighborhoods[k](perturbed)  # Executa função de vizinhança correspondente
        else:
            return None  # Fora do intervalo -> sem vizinho
    
    def _multi_objective_local_search(self, solution: Solution) -> Solution:  # Descida local multiobjetivo via pesos
        improved = copy.deepcopy(solution)  # Cópia inicial (não estraga original)
        
        weights = [random.random() for _ in range(4)]  # Gera 4 pesos aleatórios
        total = sum(weights)  # Soma total
        weights = [w / total for w in weights]  # Normaliza para somar 1
        
        maximize = [True, True, False, False]  # Indica se cada objetivo é max ou min
        
        improved = self._weighted_local_search(improved, weights, maximize)  # Executa busca local baseada em pesos
        
        return improved  # Retorna solução possivelmente melhorada
    
    def _weighted_local_search(self, solution: Solution, weights: List[float], 
                             maximize: List[bool]) -> Solution:  # Busca local iterativa
        current = copy.deepcopy(solution)  # Solução corrente
        best = copy.deepcopy(solution)  # Melhor solução encontrada
        
        best_value = self._calculate_weighted_value(best.get_objectives(), weights, maximize)  # Valor escalar inicial
        
        improved = True  # Controle do loop
        while improved:  # Continua enquanto encontra melhoria
            improved = False  # Reseta flag
            
            for neighborhood in self.neighborhoods:  # Percorre cada vizinhança
                neighbor = neighborhood(current)  # Gera vizinho
                
                if neighbor:  # Se vizinho válido
                    neighbor_value = self._calculate_weighted_value(  # Calcula valor ponderado
                        neighbor.get_objectives(), weights, maximize)
                    
                    if neighbor_value > best_value:  # Melhorou valor escalar?
                        best = copy.deepcopy(neighbor)  # Atualiza melhor
                        best_value = neighbor_value  # Atualiza valor
                        improved = True  # Marca melhoria
            
            if improved:  # Se houve melhoria nesta rodada
                current = copy.deepcopy(best)  # Atualiza ponto de partida
        
        return best  # Retorna melhor encontrado
    
    def _calculate_weighted_value(self, objectives: List[float], 
                                weights: List[float], maximize: List[bool]) -> float:  # Combina objetivos
        value = 0.0  # Acumulador
        
        for i in range(len(objectives)):  # Itera sobre cada objetivo
            obj_value = objectives[i] if maximize[i] else -objectives[i]  # Inverte sinal se objetivo de minimização
            value += weights[i] * obj_value  # Soma ponderada
        
        return value  # Retorna soma
    
    def _add_to_pareto_set(self, solution: Solution) -> bool:  # Tenta inserir solução no arquivo Pareto
        if not solution:  # Verifica validade
            return False  # Sem solução
        
        solution.objectives = solution.calculate_objectives()  # Recalcula objetivos para garantir atualizados
        
        for existing in self.pareto_set:  # Verifica se alguma existente domina a nova
            if self._dominates(existing, solution):  # Dominada -> descarta
                return False  # Não insere
        
        dominated = []  # Lista de soluções que serão removidas
        for existing in self.pareto_set:  # Checa se a nova domina alguma existente
            if self._dominates(solution, existing):  # Se sim
                dominated.append(existing)  # Marca para remoção
        
        for dominated_solution in dominated:  # Remove todas dominadas
            self.pareto_set.remove(dominated_solution)
        
        self.pareto_set.append(solution)  # Adiciona nova solução
        
        if len(self.pareto_set) > self.archive_max:  # Se excedeu limite
            self._truncate_archive()  # Aplica truncamento por crowding distance
        
        return True or len(dominated) > 0  # Sempre True (expressão redundante)
    
    def _truncate_archive(self):  # Mantém arquivo dentro do limite pelo critério de menor crowding distance
        while len(self.pareto_set) > self.archive_max:  # Enquanto exceder
            crowding_distances = self._calculate_crowding_distances()  # Calcula distâncias
            
            min_distance = float('inf')  # Inicializa menor distância
            min_index = -1  # Índice da solução a remover
            for i, distance in enumerate(crowding_distances):  # Varre distâncias
                if distance < min_distance:  # Encontra menor
                    min_distance = distance  # Atualiza menor valor
                    min_index = i  # Guarda índice
            
            if min_index >= 0:  # Se achou algum
                self.pareto_set.pop(min_index)  # Remove solução mais "aglomerada"
            else:
                self.pareto_set.pop(random.randint(0, len(self.pareto_set) - 1))  # Fallback aleatório
    
    def _calculate_crowding_distances(self) -> List[float]:  # Calcula crowding distance clássica por objetivo
        n = len(self.pareto_set)  # Número de soluções
        if n <= 2:  # Casos extremos recebem infinito
            return [float('inf')] * n  # Retorna lista de infinitos
        
        distances = [0.0] * n  # Inicializa vetores de distância
        
        for obj_idx in range(4):  # Para cada objetivo
            sorted_indices = sorted(range(n),  # Ordena índices baseado no valor do objetivo
                                  key=lambda i: self.pareto_set[i].objectives[obj_idx])
            
            distances[sorted_indices[0]] = float('inf')      # Extremidade inferior = infinito
            distances[sorted_indices[-1]] = float('inf')     # Extremidade superior = infinito
            
            obj_range = (self.pareto_set[sorted_indices[-1]].objectives[obj_idx] -  # Amplitude do objetivo
                        self.pareto_set[sorted_indices[0]].objectives[obj_idx])
            
            if obj_range > 0:  # Evita divisão por zero
                for i in range(1, n - 1):  # Ignora extremos
                    idx = sorted_indices[i]  # Índice corrente
                    prev_idx = sorted_indices[i - 1]  # Índice anterior
                    next_idx = sorted_indices[i + 1]  # Índice posterior
                    
                    distance = (self.pareto_set[next_idx].objectives[obj_idx] -  # Diferença normalizada
                              self.pareto_set[prev_idx].objectives[obj_idx]) / obj_range
                    
                    distances[idx] += distance  # Acumula distância para solução
        
        return distances  # Retorna vetores de crowding
    
    def _dominates(self, solution1: Solution, solution2: Solution) -> bool:  # Teste de dominância Pareto
        obj1 = solution1.get_objectives()  # Objetivos solução 1
        obj2 = solution2.get_objectives()  # Objetivos solução 2
        
        maximize = [True, True, False, False]  # Vetor de maximização x minimização
        
        at_least_as_good = True  # Flag: 1 é pelo menos tão boa em todos
        for i in range(len(obj1)):  # Itera objetivos
            if maximize[i]:  # Caso maximizar
                if obj1[i] < obj2[i]:  # Piorou -> falha
                    at_least_as_good = False
                    break
            else:  # Caso minimizar
                if obj1[i] > obj2[i]:  # Piorou -> falha
                    at_least_as_good = False
                    break
        
        if not at_least_as_good:  # Se não é pelo menos tão boa
            return False  # Não domina
        
        strictly_better = False  # Flag: estritamente melhor em pelo menos um objetivo
        for i in range(len(obj1)):  # Itera novamente
            if maximize[i]:  # Maximização
                if obj1[i] > obj2[i]:  # Melhor estrito
                    strictly_better = True
                    break
            else:  # Minimização
                if obj1[i] < obj2[i]:  # Melhor estrito
                    strictly_better = True
                    break
        
        return strictly_better  # Domina se melhor estrito em algum
    
    def _neighborhood_swap_within_day(self, solution: Solution) -> Optional[Solution]:  # Troca posições de duas atrações mesmo dia
        day_route = solution.day1_route if random.random() < 0.5 else solution.day2_route  # Escolhe dia aleatório
        
        if day_route.get_num_attractions() < 2:  # Precisa de pelo menos 2 atrações
            return None  # Não aplicável
        
        positions = random.sample(range(day_route.get_num_attractions()), 2)  # Seleciona 2 índices distintos
        pos1, pos2 = positions  # Desempacota
        
        modified = copy.deepcopy(solution)  # Cópia da solução
        modified_route = modified.day1_route if day_route is solution.day1_route else modified.day2_route  # Rota equivalente na cópia
        
        original_attractions = modified_route.attractions.copy()  # Guarda lista original (backup)
        original_modes = modified_route.transport_modes.copy()    # Guarda modos originais (backup)
        
        modified_route.attractions[pos1], modified_route.attractions[pos2] = \
            modified_route.attractions[pos2], modified_route.attractions[pos1]  # Realiza troca
        
        self._update_transport_modes(modified_route)  # Recalcula modos transporte conforme nova ordem
        
        self._update_route_timing(modified_route)  # Recalcula tempo e janelas
        
        if modified_route.is_valid():  # Verifica viabilidade pós-mudança
            modified.objectives = modified.calculate_objectives()  # Atualiza objetivos
            return modified  # Retorna nova solução
        
        return None  # Se inválida descarta
    
    def _neighborhood_move_between_days(self, solution: Solution) -> Optional[Solution]:  # Move uma atração para outro dia
        modified = copy.deepcopy(solution)  # Cópia independente
        
        if modified.day1_route.get_num_attractions() == 0:  # Se dia 1 vazio
            if modified.day2_route.get_num_attractions() == 0:  # E dia 2 também
                return None  # Nada a mover
            source_route = modified.day2_route  # Usa dia 2 como fonte
            target_route = modified.day1_route  # Dia 1 como destino
        elif modified.day2_route.get_num_attractions() == 0:  # Se apenas dia 2 vazio
            source_route = modified.day1_route  # Dia 1 fonte
            target_route = modified.day2_route  # Dia 2 destino
        else:  # Ambos têm atrações
            if random.random() < 0.5:  # Decide aleatoriamente direção
                source_route = modified.day1_route
                target_route = modified.day2_route
            else:
                source_route = modified.day2_route
                target_route = modified.day1_route
        
        if source_route.get_num_attractions() == 0:  # Checagem adicional de fonte vazia
            return None  # Sem movimento
        
        pos = random.randint(0, source_route.get_num_attractions() - 1)  # Seleciona índice origem
        attraction = source_route.attractions[pos]  # Obtém atração selecionada
        
        is_saturday = target_route.is_saturday  # Descobre dia alvo (sábado/domingo)
        if not attraction.is_open_on_day(is_saturday):  # Verifica se abre no dia destino
            return None  # Não pode mover
        
        source_original = source_route.attractions.copy()  # Backups listas e modos das duas rotas
        source_modes = source_route.transport_modes.copy()
        target_original = target_route.attractions.copy()
        target_modes = target_route.transport_modes.copy()
        
        source_route.attractions.pop(pos)  # Remove atração da rota fonte
        
        target_route.attractions.append(attraction)  # Adiciona no final da rota destino
        
        self._update_transport_modes(source_route)  # Atualiza modos fonte
        self._update_transport_modes(target_route)  # Atualiza modos destino
        
        self._update_route_timing(source_route)  # Recalcula tempo fonte
        self._update_route_timing(target_route)  # Recalcula tempo destino
        
        if source_route.is_valid() and target_route.is_valid():  # Valida as duas rotas
            modified.objectives = modified.calculate_objectives()  # Recalcula objetivos solução
            return modified  # Retorna nova solução
        
        source_route.attractions = source_original  # Rollback caso inválido
        source_route.transport_modes = source_modes
        target_route.attractions = target_original
        target_route.transport_modes = target_modes
        
        self._update_route_timing(source_route)  # Recalcula tempos pós rollback
        self._update_route_timing(target_route)
        
        return None  # Nenhuma solução gerada
    
    def _neighborhood_replace_attraction(self, solution: Solution) -> Optional[Solution]:  # Substitui uma atração por outra disponível
        modified = copy.deepcopy(solution)  # Cópia
        
        if modified.day1_route.get_num_attractions() == 0 and modified.day2_route.get_num_attractions() == 0:  # Sem atrações
            return None  # Não aplicável
        
        if modified.day1_route.get_num_attractions() == 0:  # Se dia 1 vazio usa dia 2
            day_route = modified.day2_route
        elif modified.day2_route.get_num_attractions() == 0:  # Vice-versa
            day_route = modified.day1_route
        else:  # Ambos têm -> escolhe aleatório
            day_route = modified.day1_route if random.random() < 0.5 else modified.day2_route
        
        if day_route.get_num_attractions() == 0:  # Segurança extra
            return None
        
        pos = random.randint(0, day_route.get_num_attractions() - 1)  # Índice da atração a substituir
        
        used_attractions = set()  # Coleta atrações já usadas na solução
        for attr in modified.day1_route.get_attractions():
            used_attractions.add(attr.name)
        for attr in modified.day2_route.get_attractions():
            used_attractions.add(attr.name)
        
        is_saturday = day_route.is_saturday  # Determina o dia
        available_attractions = (self.constructor.saturday_open_attractions if is_saturday 
                               else self.constructor.sunday_open_attractions)  # Lista de abertas
        
        available_attractions = [attr for attr in available_attractions  # Filtra para não repetidas
                               if attr.name not in used_attractions]
        
        if not available_attractions:  # Se não há alternativas
            return None
        
        original_attraction = day_route.attractions[pos]  # Guarda original
        original_attractions = day_route.attractions.copy()  # Backup lista
        original_modes = day_route.transport_modes.copy()    # Backup modos
        
        for _ in range(min(10, len(available_attractions))):  # Tenta até 10 substituições ou esgotar lista
            new_attraction = random.choice(available_attractions)  # Escolhe nova
            available_attractions.remove(new_attraction)  # Remove para não repetir tentativa
            
            day_route.attractions[pos] = new_attraction  # Substitui
            
            self._update_transport_modes(day_route)  # Recalcula modos
            
            self._update_route_timing(day_route)  # Recalcula tempos
            
            if day_route.is_valid():  # Se rota válida
                modified.objectives = modified.calculate_objectives()  # Atualiza objetivos
                return modified  # Retorna
        
        day_route.attractions[pos] = original_attraction  # Restaura original se falhou
        day_route.attractions = original_attractions
        day_route.transport_modes = original_modes
        self._update_route_timing(day_route)  # Recalcula tempos pós rollback
        
        return None  # Falhou gerar solução válida
    
    def _neighborhood_add_attraction(self, solution: Solution) -> Optional[Solution]:  # Adiciona uma nova atração
        modified = copy.deepcopy(solution)  # Cópia
        
        day1_count = modified.day1_route.get_num_attractions()  # Contagem dia 1
        day2_count = modified.day2_route.get_num_attractions()  # Contagem dia 2
        
        if day1_count < day2_count:  # Escolha de dia alvo (buscando balancear)
            day_route = modified.day1_route
        elif day2_count < day1_count:
            day_route = modified.day2_route
        else:
            day_route = modified.day1_route if random.random() < 0.5 else modified.day2_route  # Aleatório se iguais
        
        used_attractions = set()  # Coleta atrações já utilizadas
        for attr in modified.day1_route.get_attractions():
            used_attractions.add(attr.name)
        for attr in modified.day2_route.get_attractions():
            used_attractions.add(attr.name)
        
        is_saturday = day_route.is_saturday  # Dia alvo
        available_attractions = (self.constructor.saturday_open_attractions if is_saturday 
                               else self.constructor.sunday_open_attractions)  # Candidatas abertas
        
        available_attractions = [attr for attr in available_attractions  # Remove já usadas
                               if attr.name not in used_attractions]
        
        if not available_attractions:  # Sem candidatas
            return None
        
        original_attractions = day_route.attractions.copy()  # Backup
        original_modes = day_route.transport_modes.copy()    # Backup
        
        max_pos = day_route.get_num_attractions()  # Última posição possível (inserção pode ser ao final)
        pos = random.randint(0, max_pos)  # Escolhe posição de inserção
        
        for _ in range(min(10, len(available_attractions))):  # Tenta até 10 diferentes
            new_attraction = random.choice(available_attractions)  # Seleciona candidata
            available_attractions.remove(new_attraction)  # Remove da lista de tentativa
            
            day_route.attractions.insert(pos, new_attraction)  # Insere na posição escolhida
            
            self._update_transport_modes(day_route)  # Atualiza modos
            
            self._update_route_timing(day_route)  # Atualiza tempos
            
            if day_route.is_valid():  # Valida rota
                modified.objectives = modified.calculate_objectives()  # Atualiza objetivos
                return modified  # Retorna solução
            
            day_route.attractions = original_attractions.copy()  # Rollback parcial para tentar outra
        
        day_route.attractions = original_attractions  # Restaura original total
        day_route.transport_modes = original_modes
        self._update_route_timing(day_route)  # Recalcula tempos
        
        return None  # Falhou adicionar validamente
    
    def _neighborhood_remove_attraction(self, solution: Solution) -> Optional[Solution]:  # Remove atração
        modified = copy.deepcopy(solution)  # Cópia
        
        day1_count = modified.day1_route.get_num_attractions()  # Contagem dia 1
        day2_count = modified.day2_route.get_num_attractions()  # Contagem dia 2
        
        if day1_count == 0 and day2_count == 0:  # Nenhuma atração em nenhum dia
            return None  # Não aplicável
        
        if day1_count == 0:  # Escolha de rota alvo dependente das contagens
            day_route = modified.day2_route
        elif day2_count == 0:
            day_route = modified.day1_route
        elif day1_count > day2_count:
            day_route = modified.day1_route
        elif day2_count > day1_count:
            day_route = modified.day2_route
        else:
            day_route = modified.day1_route if random.random() < 0.5 else modified.day2_route  # Aleatório se igual
        
        if day_route.get_num_attractions() <= 1:  # Evita eliminar a última (critério de design)
            return None
        
        original_attractions = day_route.attractions.copy()  # Backups
        original_modes = day_route.transport_modes.copy()
        
        pos = random.randint(0, day_route.get_num_attractions() - 1)  # Índice a remover
        
        day_route.attractions.pop(pos)  # Remove efetivamente
        
        self._update_transport_modes(day_route)  # Recalcula modos pós remoção
        
        self._update_route_timing(day_route)  # Recalcula tempos
        
        if day_route.is_valid():  # Se ainda viável
            modified.objectives = modified.calculate_objectives()  # Atualiza objetivos solução
            return modified  # Retorna nova solução
        
        day_route.attractions = original_attractions  # Rollback se inválida
        day_route.transport_modes = original_modes
        self._update_route_timing(day_route)
        
        return None  # Sem solução gerada
    
    def _neighborhood_change_hotel(self, solution: Solution) -> Optional[Solution]:  # Troca hotel base
        modified = copy.deepcopy(solution)  # Cópia
        
        candidates = [hotel for hotel in self.constructor.working_hotels  # Candidatos diferentes do atual
                     if hotel.name != modified.hotel.name]
        
        if not candidates:  # Sem alternativa
            return None
        
        original_hotel = modified.hotel  # Backup hotel original
        original_day1 = copy.deepcopy(modified.day1_route)  # Backup deep rotas
        original_day2 = copy.deepcopy(modified.day2_route)
        
        for _ in range(min(10, len(candidates))):  # Tenta até 10 hotéis
            new_hotel = random.choice(candidates)  # Escolhe novo hotel
            candidates.remove(new_hotel)  # Remove para não repetir
            
            modified.hotel = new_hotel  # Aplica hotel à solução
            modified.day1_route.set_hotel(new_hotel)  # Atualiza referência na rota 1
            modified.day2_route.set_hotel(new_hotel)  # Atualiza referência na rota 2
            
            self._update_transport_modes(modified.day1_route)  # Recalcula modos rota 1
            self._update_transport_modes(modified.day2_route)  # Recalcula modos rota 2
            
            self._update_route_timing(modified.day1_route)  # Recalcula tempos rota 1
            self._update_route_timing(modified.day2_route)  # Recalcula tempos rota 2
            
            if modified.day1_route.is_valid() and modified.day2_route.is_valid():  # Ambas viáveis
                modified.objectives = modified.calculate_objectives()  # Atualiza objetivos
                return modified  # Retorna solução
        
        modified.hotel = original_hotel  # Rollback hotel
        modified.day1_route = original_day1  # Rollback rotas
        modified.day2_route = original_day2
        
        return None  # Falhou trocar
    
    def _neighborhood_change_transport(self, solution: Solution) -> Optional[Solution]:  # Altera modo de transporte de um segmento
        modified = copy.deepcopy(solution)  # Cópia
        
        day_route = modified.day1_route if random.random() < 0.5 else modified.day2_route  # Escolhe rota aleatória
        
        if len(day_route.transport_modes) == 0:  # Sem segmentos
            return None
        
        segment_idx = random.randint(0, len(day_route.transport_modes) - 1)  # Índice do segmento
        
        current_mode = day_route.transport_modes[segment_idx]  # Modo atual
        
        if segment_idx == 0:  # Segmento hotel -> primeira atração
            from_name = modified.hotel.name
            to_name = day_route.attractions[0].name if day_route.attractions else modified.hotel.name
        elif segment_idx < len(day_route.attractions):  # Segmento entre atrações internas
            from_name = day_route.attractions[segment_idx - 1].name
            to_name = day_route.attractions[segment_idx].name
        else:  # Segmento final última atração -> hotel
            from_name = day_route.attractions[-1].name
            to_name = modified.hotel.name
        
        all_modes = [TransportMode.WALK, TransportMode.BUS_WALK,  # Lista completa de modos considerados
                    TransportMode.SUBWAY_WALK, TransportMode.CAR]
        
        if current_mode in all_modes:  # Remove modo atual para evitar escolha redundante
            all_modes.remove(current_mode)
        
        valid_modes = []  # Lista de modos alternativos viáveis
        for mode in all_modes:  # Testa cada modo
            travel_time = self._get_travel_time(from_name, to_name, mode)  # Obtém tempo de viagem
            if travel_time >= 0:  # Tempo válido (>=0 indica existência de percurso)
                valid_modes.append(mode)  # Adiciona modo alternativo
        
        if not valid_modes:  # Se não há alternativa
            return None
        
        new_mode = random.choice(valid_modes)  # Escolhe novo modo disponível
        
        original_modes = day_route.transport_modes.copy()  # Backup lista de modos
        
        day_route.transport_modes[segment_idx] = new_mode  # Aplica mudança
        
        self._update_route_timing(day_route)  # Recalcula tempos (impacto em cronograma)
        
        if day_route.is_valid():  # Se rota segue válida
            modified.objectives = modified.calculate_objectives()  # Atualiza objetivos
            return modified  # Retorna solução
        
        day_route.transport_modes = original_modes  # Rollback se inválido
        self._update_route_timing(day_route)  # Recalcula tempos pós rollback
        
        return None  # Falhou trocar
    
    def _update_transport_modes(self, day_route: DailyRoute) -> None:  # Reconstrói sequência completa de modos
        day_route.transport_modes = []  # Reseta lista
        
        if not day_route.attractions:  # Se não há atrações nada a fazer
            return
        
        first_attr = day_route.attractions[0]  # Primeira atração do dia
        valid_modes = self._get_valid_transport_modes(day_route.hotel.name, first_attr.name)  # Modos válidos hotel->1ª
        if valid_modes:  # Se há modos possíveis
            mode = self._choose_preferred_mode(valid_modes)  # Escolhe preferido
            day_route.transport_modes.append(mode)  # Adiciona
        else:
            day_route.transport_modes.append(TransportMode.CAR)  # Fallback CAR
        
        for i in range(len(day_route.attractions) - 1):  # Para cada par consecutivo de atrações
            from_attr = day_route.attractions[i]
            to_attr = day_route.attractions[i+1]
            valid_modes = self._get_valid_transport_modes(from_attr.name, to_attr.name)  # Modos válidos
            if valid_modes:
                mode = self._choose_preferred_mode(valid_modes)
                day_route.transport_modes.append(mode)
            else:
                day_route.transport_modes.append(TransportMode.CAR)
        
        last_attr = day_route.attractions[-1]  # Última atração
        valid_modes = self._get_valid_transport_modes(last_attr.name, day_route.hotel.name)  # Volta ao hotel
        if valid_modes:
            mode = self._choose_preferred_mode(valid_modes)
            day_route.transport_modes.append(mode)
        else:
            day_route.transport_modes.append(TransportMode.CAR)
    
    def _update_route_timing(self, day_route: DailyRoute) -> None:  # Recalcula estrutura temporal da rota
        day_route.time_info = []  # Limpa registros anteriores
        day_route.recalculate_time_info()  # Chama método da rota para recomputar janelas e tempos
    
    def _get_valid_transport_modes(self, from_name: str, to_name: str) -> List[TransportMode]:  # Determina modos possíveis entre dois pontos
        cache_key = (from_name, to_name)  # Chave para cache
        if cache_key in self._mode_validity_cache:  # Verifica cache
            return self._mode_validity_cache[cache_key]  # Retorna cacheado
        
        valid_modes = []  # Lista acumuladora
        for mode in [TransportMode.WALK, TransportMode.BUS_WALK,  # Testa todos os modos suportados
                    TransportMode.SUBWAY_WALK, TransportMode.CAR]:
            travel_time = self._get_travel_time(from_name, to_name, mode)  # Tempo do deslocamento
            if travel_time >= 0:  # Se válido
                valid_modes.append(mode)  # Adiciona
        
        self._mode_validity_cache[cache_key] = valid_modes  # Armazena no cache
        return valid_modes  # Retorna lista
    
    def _get_travel_time(self, from_name: str, to_name: str, mode: TransportMode) -> float:  # Wrapper para utilitário de tempo
        from utils import Transport  # Import local (evita ciclos no topo)
        return Transport.get_travel_time(from_name, to_name, mode)  # Chama método estático
    
    def _choose_preferred_mode(self, valid_modes: List[TransportMode]) -> TransportMode:  # Heurística escolha de modo
        if not valid_modes:  # Lista vazia -> fallback
            return TransportMode.CAR
        
        if TransportMode.WALK in valid_modes:  # Prioriza caminhar
            return TransportMode.WALK
        
        if TransportMode.SUBWAY_WALK in valid_modes:  # Depois metrô
            return TransportMode.SUBWAY_WALK
        
        if TransportMode.BUS_WALK in valid_modes:  # Depois ônibus
            return TransportMode.BUS_WALK
        
        if TransportMode.CAR in valid_modes:  # Depois carro
            return TransportMode.CAR
        
        return valid_modes[0]  # Último fallback (não esperado)
    
    def _calculate_initial_metrics(self, solutions: List[Solution]) -> Dict:  # Calcula métricas agregadas da população inicial
        metrics = {  # Estrutura de métricas com iniciais extremos
            "min_attractions": float('inf'),
            "max_attractions": 0,
            "avg_attractions": 0,
            "min_quality": float('inf'),
            "max_quality": 0,
            "avg_quality": 0,
            "min_time": float('inf'),
            "max_time": 0,
            "avg_time": 0,
            "min_cost": float('inf'),
            "max_cost": 0,
            "avg_cost": 0
        }
        
        total_attractions = 0  # Acumuladores para médias
        total_quality = 0
        total_time = 0
        total_cost = 0
        
        for solution in solutions:  # Percorre cada solução inicial
            objectives = solution.get_objectives()  # Obtém vetores de objetivos
            
            attractions = objectives[0]  # Número de atrações
            metrics["min_attractions"] = min(metrics["min_attractions"], attractions)  # Atualiza mínimo
            metrics["max_attractions"] = max(metrics["max_attractions"], attractions)  # Atualiza máximo
            total_attractions += attractions  # Soma total
            
            quality = objectives[1]  # Qualidade total
            metrics["min_quality"] = min(metrics["min_quality"], quality)
            metrics["max_quality"] = max(metrics["max_quality"], quality)
            total_quality += quality
            
            time_val = objectives[2]  # Tempo total
            metrics["min_time"] = min(metrics["min_time"], time_val)
            metrics["max_time"] = max(metrics["max_time"], time_val)
            total_time += time_val
            
            cost = objectives[3]  # Custo total
            metrics["min_cost"] = min(metrics["min_cost"], cost)
            metrics["max_cost"] = max(metrics["max_cost"], cost)
            total_cost += cost
            
            self._update_best_solutions(solution)  # Atualiza melhores individuais
        
        if solutions:  # Evita divisão por zero
            count = len(solutions)  # Quantidade
            metrics["avg_attractions"] = total_attractions / count  # Média atrações
            metrics["avg_quality"] = total_quality / count          # Média qualidade
            metrics["avg_time"] = total_time / count                # Média tempo
            metrics["avg_cost"] = total_cost / count                # Média custo
        
        return metrics  # Retorna dicionário
    
    def _calculate_iteration_metrics(self, iteration: int, elapsed_time: float) -> Dict:  # Métricas referentes à frente atual
        metrics = {  # Estrutura com acumuladores / extremos
            "iteration": iteration,
            "elapsed_time": elapsed_time,
            "pareto_size": len(self.pareto_set),
            "min_attractions": float('inf'),
            "max_attractions": 0,
            "avg_attractions": 0,
            "min_quality": float('inf'),
            "max_quality": 0,
            "avg_quality": 0,
            "min_time": float('inf'),
            "max_time": 0,
            "avg_time": 0,
            "min_cost": float('inf'),
            "max_cost": 0,
            "avg_cost": 0
        }
        
        total_attractions = 0  # Acumuladores
        total_quality = 0
        total_time = 0
        total_cost = 0
        
        for solution in self.pareto_set:  # Percorre soluções Pareto
            objectives = solution.get_objectives()  # Obtém objetivos
            
            attractions = objectives[0]  # Atrações
            metrics["min_attractions"] = min(metrics["min_attractions"], attractions)
            metrics["max_attractions"] = max(metrics["max_attractions"], attractions)
            total_attractions += attractions
            
            quality = objectives[1]  # Qualidade
            metrics["min_quality"] = min(metrics["min_quality"], quality)
            metrics["max_quality"] = max(metrics["max_quality"], quality)
            total_quality += quality
            
            time_val = objectives[2]  # Tempo
            metrics["min_time"] = min(metrics["min_time"], time_val)
            metrics["max_time"] = max(metrics["max_time"], time_val)
            total_time += time_val
            
            cost = objectives[3]  # Custo
            metrics["min_cost"] = min(metrics["min_cost"], cost)
            metrics["max_cost"] = max(metrics["max_cost"], cost)
            total_cost += cost
            
            self._update_best_solutions(solution)  # Atualiza melhores
        
        if self.pareto_set:  # Se há soluções
            count = len(self.pareto_set)  # Tamanho
            metrics["avg_attractions"] = total_attractions / count
            metrics["avg_quality"] = total_quality / count
            metrics["avg_time"] = total_time / count
            metrics["avg_cost"] = total_cost / count
        
        return metrics  # Retorna métricas
    
    def _update_best_solutions(self, solution: Solution) -> None:  # Atualiza registro de melhores soluções individuais
        objectives = solution.get_objectives()  # Objetivos atuais
        
        if "attractions" not in self.best_solutions or \
           objectives[0] > self.best_solutions["attractions"].get_objectives()[0]:  # Melhor número de atrações
            self.best_solutions["attractions"] = copy.deepcopy(solution)
        
        if "quality" not in self.best_solutions or \
           objectives[1] > self.best_solutions["quality"].get_objectives()[1]:  # Melhor qualidade
            self.best_solutions["quality"] = copy.deepcopy(solution)
        
        if "time" not in self.best_solutions or \
           objectives[2] < self.best_solutions["time"].get_objectives()[2]:  # Menor tempo
            self.best_solutions["time"] = copy.deepcopy(solution)
        
        if "cost" not in self.best_solutions or \
           objectives[3] < self.best_solutions["cost"].get_objectives()[3]:  # Menor custo
            self.best_solutions["cost"] = copy.deepcopy(solution)
    
    def export_results(self, pareto_file: str, metrics_file: str) -> bool:  # Exporta frente Pareto e métricas
        try:  # Bloco de tratamento de erros de IO
            import os  # Import local (evita dependência global desnecessária)
            pareto_dir = os.path.dirname(pareto_file)  # Diretório do arquivo de soluções
            metrics_dir = os.path.dirname(metrics_file)  # Diretório do arquivo de métricas
            
            if pareto_dir and not os.path.exists(pareto_dir):  # Cria diretório se não existir
                os.makedirs(pareto_dir)
            
            if metrics_dir and not os.path.exists(metrics_dir):  # Cria diretório de métricas
                os.makedirs(metrics_dir)
            
            sorted_pareto = sorted(self.pareto_set, key=lambda s: s.get_objectives()[0], reverse=True)  # Ordena por nº atrações desc
            
            with open(pareto_file, 'w', newline='', encoding='utf-8') as file:  # Abre arquivo soluções
                file.write("Solution;Hotel;HotelRating;HotelPrice;TotalAttractions;TotalQuality;TotalTime;TotalCost;"  # Cabeçalho CSV
                          "Day1Attractions;Day1Neighborhoods;Day1Time;Day1Cost;Day2Attractions;Day2Neighborhoods;"
                          "Day2Time;Day2Cost;Day1Sequence;Day1TransportModes;Day2Sequence;Day2TransportModes\n")
                
                for i, solution in enumerate(sorted_pareto):  # Itera soluções ordenadas
                    try:  # Protege erro em solução isolada
                        solution.objectives = solution.calculate_objectives()  # Recalcula objetivos para consistência
                        
                        hotel = solution.hotel  # Referência hotel
                        day1 = solution.day1_route  # Rota dia 1
                        day2 = solution.day2_route  # Rota dia 2
                        objectives = solution.get_objectives()  # Vetor objetivos
                        
                        day1_modes = []  # Lista textual modos dia 1
                        day1_attractions = day1.get_attractions()  # Atrações dia 1
                        day1_transport_modes = day1.get_transport_modes()  # Modos transporte dia 1
                        
                        for j in range(len(day1_transport_modes)):  # Converte enum para string
                            day1_modes.append(TransportMode.get_mode_string(day1_transport_modes[j]))
                        
                        day2_modes = []  # Lista textual modos dia 2
                        day2_attractions = day2.get_attractions()  # Atrações dia 2
                        day2_transport_modes = day2.get_transport_modes()  # Modos transporte dia 2
                        
                        for j in range(len(day2_transport_modes)):  # Converte enum para string
                            day2_modes.append(TransportMode.get_mode_string(day2_transport_modes[j]))
                        
                        file.write(f"{i + 1};")  # Índice solução
                        file.write(f"{hotel.name};")  # Nome hotel
                        file.write(f"{hotel.rating:.1f};")  # Nota hotel
                        file.write(f"{hotel.price:.2f};")  # Preço hotel
                        file.write(f"{objectives[0]:.0f};")  # Total atrações
                        file.write(f"{objectives[1]:.1f};")  # Qualidade
                        file.write(f"{objectives[2]:.1f};")  # Tempo total
                        file.write(f"{objectives[3]:.2f};")  # Custo total
                        
                        file.write(f"{day1.get_num_attractions()};")  # Nº atrações dia 1
                        file.write(f"{len(day1.get_neighborhoods())};")  # Nº bairros/zona (se existir conceito)
                        file.write(f"{day1.get_total_time():.1f};")  # Tempo dia 1
                        file.write(f"{day1.get_total_cost():.2f};")  # Custo dia 1
                        
                        file.write(f"{day2.get_num_attractions()};")  # Nº atrações dia 2
                        file.write(f"{len(day2.get_neighborhoods())};")  # Nº bairros dia 2
                        file.write(f"{day2.get_total_time():.1f};")  # Tempo dia 2
                        file.write(f"{day2.get_total_cost():.2f};")  # Custo dia 2
                        
                        file.write("|".join(attr.name for attr in day1.get_attractions()) + ";")  # Sequência nomes dia 1
                        file.write("|".join(day1_modes) + ";")  # Modos concatenados dia 1
                        file.write("|".join(attr.name for attr in day2.get_attractions()) + ";")  # Sequência nomes dia 2
                        file.write("|".join(day2_modes) + "\n")  # Modos concatenados dia 2 + quebra linha
                    except Exception as e:  # Captura erro exportando uma solução
                        print(f"Error exporting solution {i+1}: {str(e)}")  # Log de erro
                        continue  # Prossegue com a próxima
            
            with open(metrics_file, 'w', newline='', encoding='utf-8') as file:  # Abre arquivo métricas
                file.write("Iteration;ParetoSize;Time;MinAttr;MaxAttr;AvgAttr;MinQuality;"  # Cabeçalho métricas
                          "MaxQuality;AvgQuality;MinTime;MaxTime;AvgTime;MinCost;MaxCost;AvgCost\n")
                
                for metrics in self.iteration_metrics:  # Itera métricas coletadas
                    file.write(f"{metrics['iteration']};")  # Iteração
                    file.write(f"{metrics['pareto_size']};")  # Tamanho Pareto
                    file.write(f"{metrics['elapsed_time']:.2f};")  # Tempo gasto
                    file.write(f"{metrics['min_attractions']:.0f};")  # Min atrações
                    file.write(f"{metrics['max_attractions']:.0f};")  # Max atrações
                    file.write(f"{metrics['avg_attractions']:.2f};")  # Média atrações
                    file.write(f"{metrics['min_quality']:.1f};")  # Min qualidade
                    file.write(f"{metrics['max_quality']:.1f};")  # Max qualidade
                    file.write(f"{metrics['avg_quality']:.2f};")  # Média qualidade
                    file.write(f"{metrics['min_time']:.1f};")  # Min tempo
                    file.write(f"{metrics['max_time']:.1f};")  # Max tempo
                    file.write(f"{metrics['avg_time']:.2f};")  # Média tempo
                    file.write(f"{metrics['min_cost']:.2f};")  # Min custo
                    file.write(f"{metrics['max_cost']:.2f};")  # Max custo
                    file.write(f"{metrics['avg_cost']:.2f}\n")  # Média custo + quebra
            
            print(f"Results exported to {pareto_file} and {metrics_file}")  # Log sucesso exportação
            return True  # Operação concluída
        except Exception as e:  # Captura exceções gerais
            print(f"Error exporting results: {str(e)}")  # Log erro principal
            import traceback  # Import para stack trace
            traceback.print_exc()  # Exibe traceback completo
            return False  # Indica falha
