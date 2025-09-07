# -*- coding: utf-8 -*-
"""
Versão comentada linha a linha de movns/metrics.py.
Objetivo: explicar cada instrução dos indicadores multiobjetivo (hipervolume, spread, epsilon,...).
A lógica foi preservada exatamente; apenas comentários foram adicionados.
"""

import numpy as np  # Biblioteca numérica para vetores/matrizes
from typing import List, Tuple, Dict, Any, Optional  # Tipagem estática opcional
import copy  # Pode ser útil para cópias (preservado do original)
import random  # Amostragem aleatória
import time  # Controle de cache por tempo
from functools import cmp_to_key  # Mantido para compatibilidade (mesmo que não usado diretamente)


class MultiObjectiveMetrics:
    """Coleção de funções estáticas para calcular métricas multiobjetivo."""

    @staticmethod
    def normalize_objectives(solutions: List[Any],
                           objective_indices: List[int],
                           maximize: List[bool],
                           reference_point: Optional[List[float]] = None) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        objectives = np.array([
            [solution.get_objectives()[idx] for idx in objective_indices]  # Seleciona objetivos por índice
            for solution in solutions  # Para cada solução
        ])

        if len(objectives) == 0:  # Se não há soluções
            return np.array([]), np.array([]), np.array([])  # Retorna arrays vazios

        min_values = np.min(objectives, axis=0)  # Mínimos por objetivo
        max_values = np.max(objectives, axis=0)  # Máximos por objetivo

        if reference_point is not None:  # Se há ponto de referência
            ref_point = np.array([reference_point[idx] for idx in objective_indices])  # Extrai componente correspondente
            for i in range(len(objective_indices)):
                if maximize[i]:  # Para objetivos de maximização, o mínimo pode ser reduzido pelo ref
                    min_values[i] = min(min_values[i], ref_point[i])
                else:  # Para minimização, o máximo pode ser elevado pelo ref
                    max_values[i] = max(max_values[i], ref_point[i])

        ranges = max_values - min_values  # Amplitudes por objetivo

        for i in range(len(ranges)):  # Evita divisão por zero na normalização
            if ranges[i] == 0:
                ranges[i] = 1.0

        normalized = np.zeros_like(objectives, dtype=float)  # Aloca matriz normalizada
        for i in range(len(solutions)):  # Para cada solução
            for j in range(len(objective_indices)):  # Para cada objetivo selecionado
                if maximize[j]:  # Normaliza para [0,1] onde 1 é melhor
                    normalized[i, j] = (objectives[i, j] - min_values[j]) / ranges[j]
                else:  # Para minimizar, inverte a escala
                    normalized[i, j] = 1 - (objectives[i, j] - min_values[j]) / ranges[j]

        return normalized, min_values, max_values  # Retorna normalizados e limites (para debug ou uso posterior)

    # Estruturas de cache de hipervolume
    _hypervolume_cache = {}  # Dict para memoização pelo conjunto de objetivos
    _cache_hits = 0  # Contador de acertos
    _cache_misses = 0  # Contador de faltas
    _last_cache_clear = time.time()  # Timestamp da última limpeza

    @staticmethod
    def calculate_hypervolume(solutions: List[Any],
                            objective_indices: List[int] = [0, 1, 2, 3],
                            maximize: List[bool] = [True, True, False, False],
                            reference_point: Optional[List[float]] = None) -> float:
        if not solutions:  # Se não há soluções
            return 0.0  # HV nulo

        current_time = time.time()  # Agora
        if current_time - MultiObjectiveMetrics._last_cache_clear > 300:  # Limpa cache a cada 5 min
            MultiObjectiveMetrics._hypervolume_cache.clear()  # Limpa
            MultiObjectiveMetrics._last_cache_clear = current_time  # Atualiza relógio
            MultiObjectiveMetrics._cache_hits = 0  # Zera contadores
            MultiObjectiveMetrics._cache_misses = 0

        objectives_tuples = []  # Lista de tuplas de objetivos selecionados
        for solution in solutions:  # Para cada solução
            objectives = solution.get_objectives()  # Vetor de objetivos
            selected_objectives = tuple(objectives[idx] for idx in objective_indices)  # Seleciona índices
            objectives_tuples.append(selected_objectives)  # Empilha tupla

        objectives_tuples.sort()  # Ordena para ter chave determinística
        cache_key = (  # Monta chave de cache incluindo parâmetros
            tuple(objectives_tuples),
            tuple(objective_indices),
            tuple(maximize),
            tuple(reference_point) if reference_point is not None else None
        )

        if cache_key in MultiObjectiveMetrics._hypervolume_cache:  # Se já calculado
            MultiObjectiveMetrics._cache_hits += 1  # Conta acerto
            return MultiObjectiveMetrics._hypervolume_cache[cache_key]  # Retorna valor cacheado

        MultiObjectiveMetrics._cache_misses += 1  # Conta falta de cache

        # Amostragem para conjuntos grandes em alta dimensão
        if len(solutions) > 20 and len(objective_indices) > 3:
            sampled_solutions = MultiObjectiveMetrics._sample_representative_solutions(
                solutions, objective_indices, maximize, max_size=20
            )  # Seleciona subconjunto representativo
            normalized, _, _ = MultiObjectiveMetrics.normalize_objectives(
                sampled_solutions, objective_indices, maximize, reference_point
            )  # Normaliza subconjunto
        else:
            normalized, _, _ = MultiObjectiveMetrics.normalize_objectives(
                solutions, objective_indices, maximize, reference_point
            )  # Normaliza conjunto completo

        if normalized.size == 0:  # Segurança
            return 0.0

        ref_point = np.zeros(len(objective_indices))  # Usa ponto de referência (0,0,...) no espaço normalizado

        hypervolume = MultiObjectiveMetrics._hypervolume_exact(normalized, ref_point)  # Calcula HV exato/approx

        MultiObjectiveMetrics._hypervolume_cache[cache_key] = hypervolume  # Salva no cache

        return hypervolume  # Retorna HV

    @staticmethod
    def _sample_representative_solutions(solutions: List[Any],
                                       objective_indices: List[int],
                                       maximize: List[bool],
                                       max_size: int = 20) -> List[Any]:
        if len(solutions) <= max_size:  # Se já está no limite
            return solutions  # Retorna como está

        objectives = np.array([
            [solution.get_objectives()[idx] for idx in objective_indices]
            for solution in solutions
        ])  # Matriz de objetivos

        sampled_indices = set()  # Conjunto de índices amostrados

        for i, obj_index in enumerate(objective_indices):  # Para cada objetivo
            if maximize[i]:  # Seleciona melhor e pior naquele objetivo
                best_idx = np.argmax(objectives[:, i])
                worst_idx = np.argmin(objectives[:, i])
            else:
                best_idx = np.argmin(objectives[:, i])
                worst_idx = np.argmax(objectives[:, i])

            sampled_indices.add(best_idx)  # Garante extremos
            sampled_indices.add(worst_idx)

        remaining_indices = list(set(range(len(solutions))) - sampled_indices)  # Restantes
        if len(remaining_indices) > max_size - len(sampled_indices):  # Se ainda excede, amostra aleatoriamente
            random_indices = random.sample(remaining_indices, max_size - len(sampled_indices))
            sampled_indices.update(random_indices)
        else:
            sampled_indices.update(remaining_indices)  # Cabe todos restantes

        return [solutions[i] for i in sampled_indices]  # Reconstrói lista de soluções selecionadas

    @staticmethod
    def _hypervolume_exact(points: np.ndarray, reference_point: np.ndarray) -> float:
        if len(points) == 0:  # Sem pontos
            return 0.0  # HV nulo

        valid_points = []  # Pontos acima do ref (dominantes no espaço [0,1])
        for point in points:
            if np.all(point >= reference_point) and np.any(point > reference_point):  # Pelo menos um estritamente maior
                valid_points.append(point)

        if not valid_points:  # Se nenhum ponto válido
            return 0.0001  # Retorna quase-zero para estabilizar indicadores

        points = np.array(valid_points)  # Converte lista em array

        if len(points) == 1:  # Um único ponto
            return np.prod(np.abs(points[0] - reference_point))  # Volume do paralelepípedo até ref

        if points.shape[1] == 2:  # Caso 2D, cálculo por varredura
            sorted_points = points[points[:, 0].argsort()[::-1]]  # Ordena por x desc

            hv = 0.0  # Acumulador de área
            prev_x = sorted_points[0, 0]  # Último x considerado
            prev_y = reference_point[1]  # y de referência inicial

            for point in sorted_points:  # Para cada ponto
                x, y = point  # Desempacota
                if y > prev_y:  # Se y aumenta, adiciona área do retângulo
                    hv += (prev_x - reference_point[0]) * (y - prev_y)
                    prev_y = y  # Atualiza y anterior

                prev_x = min(prev_x, x)  # Garante monotonicidade de x

            if prev_x > reference_point[0]:  # Última faixa até ref
                hv += (prev_x - reference_point[0]) * (1.0 - prev_y)

            return max(0.0001, hv)  # Garante mínimo numérico

        if points.shape[1] == 3:  # Caso 3D, integração em fatias z
            if points.shape[0] <= 10:  # Poucos pontos -> recursão exata
                return max(0.0001, MultiObjectiveMetrics._hypervolume_recursive(
                    points, reference_point, points.shape[1] - 1))

            sorted_indices = np.argsort(points[:, 2])[::-1]  # Ordena por z desc
            sorted_points = points[sorted_indices]  # Aplica ordenação

            hv = 0.0  # Acumulador volume
            prev_z = reference_point[2]  # z inicial

            z_values = np.unique(sorted_points[:, 2])  # Níveis únicos de z

            if len(z_values) == 1:  # Todos no mesmo z
                z = z_values[0]
                if z > reference_point[2]:  # Se acima do ref
                    slice_area = MultiObjectiveMetrics._hypervolume_exact(
                        sorted_points[:, 0:2], reference_point[0:2])  # Área 2D nessa fatia
                    hv = slice_area * (z - reference_point[2])  # Volume = área * altura
            else:
                slice_area = 0.0  # Área da fatia atual
                last_processed_idx = -1  # Último índice processado para evitar recomputação

                for z in z_values:  # Para cada nível z
                    if z <= reference_point[2]:  # Ignora abaixo do ref
                        continue

                    z_level_indices = np.where(sorted_points[:, 2] >= z)[0]  # Índices com z>=nível
                    max_idx = np.max(z_level_indices)  # Último índice incluído

                    if max_idx > last_processed_idx:  # Se expandiu conjunto de pontos
                        slice_points = sorted_points[:max_idx+1, 0:2]  # Pega pontos até max_idx em 2D
                        slice_area = MultiObjectiveMetrics._hypervolume_exact(
                            slice_points, reference_point[0:2])  # Recalcula área 2D
                        last_processed_idx = max_idx  # Atualiza marcador

                    if z > prev_z:  # Integra volume entre prev_z e z
                        hv += slice_area * (z - prev_z)  # Soma volume
                        prev_z = z  # Atualiza z anterior

            return max(0.0001, hv)  # Retorna volume com piso numérico

        if points.shape[1] >= 4:  # 4D ou mais -> Monte Carlo
            return max(0.0001, MultiObjectiveMetrics._hypervolume_monte_carlo(
                points, reference_point, samples=10000))

        # Fallback geral: recursivo para dimensão arbitrária
        return max(0.0001, MultiObjectiveMetrics._hypervolume_recursive(
            points, reference_point, points.shape[1] - 1))

    @staticmethod
    def _hypervolume_monte_carlo(points: np.ndarray, reference_point: np.ndarray, samples: int = 20000) -> float:
        ndim = points.shape[1]  # Dimensionalidade
        npoints = points.shape[0]  # Nº de pontos

        max_values = np.max(points, axis=0)  # Limite superior do hipercubo de amostragem

        total_volume = np.prod(max_values - reference_point)  # Volume do hipercubo

        if total_volume <= 0:  # Caso degenerado
            return 0.0001

        if npoints == 1:  # Um ponto -> volume direto
            return np.prod(points[0] - reference_point)

        adaptive_samples = min(30000, samples * (1 + int(npoints/10)))  # Ajuste do nº de amostras

        chunk_size = min(5000, adaptive_samples)  # Tamanho de bloco para reduzir memória
        dominated_count = 0  # Contador de amostras dominadas

        for i in range(0, adaptive_samples, chunk_size):  # Processa em blocos
            current_chunk_size = min(chunk_size, adaptive_samples - i)  # Tamanho real deste bloco
            chunk_samples = np.random.uniform(  # Amostra uniforme no hipercubo
                low=reference_point,
                high=max_values,
                size=(current_chunk_size, ndim)
            )

            for sample in chunk_samples:  # Para cada amostra
                is_dominated = False  # Flag de dominância

                point_batch_size = 50  # Processa pontos em lotes
                for j in range(0, npoints, point_batch_size):  # Varre pontos em batches
                    end_idx = min(j + point_batch_size, npoints)  # Fim do batch
                    current_points = points[j:end_idx]  # Pedaço de pontos

                    dominance = np.all(current_points >= sample, axis=1)  # Teste de dominância por amostra

                    if np.any(dominance):  # Se algum ponto domina a amostra
                        is_dominated = True  # Marca como dominada
                        break  # Sai do loop de pontos

                if is_dominated:  # Após checagem dos pontos
                    dominated_count += 1  # Incrementa contador

        dominated_fraction = dominated_count / adaptive_samples  # Fração de amostras dominadas
        hypervolume = dominated_fraction * total_volume  # HV estimado

        if adaptive_samples < 10000:  # Correção leve para amostragem pequena
            correction = 0.005 * total_volume
            hypervolume = min(total_volume, hypervolume + correction)

        return max(0.0001, hypervolume)  # Garante piso numérico

    @staticmethod
    def _hypervolume_recursive(points: np.ndarray,
                             reference_point: np.ndarray,
                             dimension: int) -> float:
        if dimension == 0:  # Base recursiva 1D
            if len(points) == 0:  # Sem pontos
                return 0.0
            return np.max(points[:, 0] - reference_point[0])  # Maior distância ao ref

        sorted_indices = np.argsort(points[:, dimension])[::-1]  # Ordena por última dimensão desc
        sorted_points = points[sorted_indices]  # Aplica ordenação

        hv = 0.0  # Acumulador
        prev_h = reference_point[dimension]  # Nível inicial

        for i in range(len(sorted_points)):  # Para cada fatia
            h = sorted_points[i, dimension]  # Altura da fatia atual
            if h > prev_h:  # Se avançamos em relação à altura anterior
                dominated = []  # Coleção de pontos dominantes na subdimensão
                for j in range(i + 1):  # Pega pontos até i (inclusivo)
                    if all(sorted_points[j, :dimension] >= reference_point[:dimension]):  # Condição válida
                        dominated.append(sorted_points[j, :dimension])  # Adiciona projeção  (dim-1)

                hv += (h - prev_h) * MultiObjectiveMetrics._hypervolume_recursive(  # Integra volume nesta faixa
                    np.array(dominated) if dominated else np.empty((0, dimension)),  # Conjunto de projeções
                    reference_point[:dimension],  # Ref projetado
                    dimension - 1  # Reduz dimensão
                )

                prev_h = h  # Atualiza nível anterior

        return max(0.0001, hv)  # Retorna com piso numérico

    @staticmethod
    def calculate_hypervolume_contribution(solutions: List[Any],
                                         solution_index: int,
                                         objective_indices: List[int] = [0, 1, 2, 3],
                                         maximize: List[bool] = [True, True, False, False],
                                         reference_point: Optional[List[float]] = None) -> float:
        if not solutions or solution_index < 0 or solution_index >= len(solutions):  # Validação
            return 0.0

        total_hv = MultiObjectiveMetrics.calculate_hypervolume(  # HV do conjunto completo
            solutions, objective_indices, maximize, reference_point)

        reduced_solutions = [solutions[i] for i in range(len(solutions)) if i != solution_index]  # Remove uma solução

        reduced_hv = MultiObjectiveMetrics.calculate_hypervolume(  # HV do conjunto reduzido
            reduced_solutions, objective_indices, maximize, reference_point)

        return max(0.0, total_hv - reduced_hv)  # Contribuição marginal >= 0

    @staticmethod
    def calculate_spread_indicator(solutions: List[Any],
                                 objective_indices: List[int] = [0, 1, 2, 3],
                                 maximize: List[bool] = [True, True, False, False]) -> float:
        if len(solutions) < 2:  # Requer ao menos duas soluções
            return 0.0

        normalized, _, _ = MultiObjectiveMetrics.normalize_objectives(  # Normaliza no hipercubo [0,1]^m
            solutions, objective_indices, maximize)

        centroid = np.mean(normalized, axis=0)  # Centroide da frente

        distances_from_centroid = np.sqrt(np.sum((normalized - centroid) ** 2, axis=1))  # Distâncias ao centroide
        sorted_indices = np.argsort(distances_from_centroid)  # Ordena por distância
        sorted_points = normalized[sorted_indices]  # Pontos ordenados

        distances = np.sqrt(np.sum((sorted_points[1:] - sorted_points[:-1]) ** 2, axis=1))  # Distâncias adjacentes

        mean_distance = np.mean(distances) if len(distances) > 0 else 0.0  # Distância média

        extreme_distances = []  # Distâncias aos extremos para cada objetivo
        for i in range(len(objective_indices)):
            min_idx = np.argmin(normalized[:, i])  # Índice do extremo inferior
            max_idx = np.argmax(normalized[:, i])  # Índice do extremo superior

            min_dists = np.sqrt(np.sum((normalized - normalized[min_idx]) ** 2, axis=1))  # Distâncias ao mínimo
            min_dists[min_idx] = float('inf')  # Ignora ponto para evitar zero
            extreme_distances.append(np.min(min_dists))  # Menor distância ao mínimo

            max_dists = np.sqrt(np.sum((normalized - normalized[max_idx]) ** 2, axis=1))  # Distâncias ao máximo
            max_dists[max_idx] = float('inf')  # Ignora ele mesmo
            extreme_distances.append(np.min(max_dists))  # Menor distância ao máximo

        df = np.sum(extreme_distances)  # Soma distâncias aos extremos
        di_sum = np.sum(np.abs(distances - mean_distance))  # Soma desvios à média

        denominator = df + (len(solutions) - 1) * mean_distance  # Denominador da fórmula (evita divisão por zero)
        if denominator == 0:
            return 0.0

        spread = (df + di_sum) / denominator  # Indicador final
        return spread  # Retorna

    @staticmethod
    def calculate_epsilon_indicator(solutions1: List[Any],
                                  solutions2: List[Any],
                                  objective_indices: List[int] = [0, 1, 2, 3],
                                  maximize: List[bool] = [True, True, False, False]) -> float:
        if not solutions1 or not solutions2:  # Precisa de dois conjuntos
            return 0.0

        objectives1 = np.array([
            [solution.get_objectives()[idx] for idx in objective_indices]  # Seleciona objetivos
            for solution in solutions1
        ])

        objectives2 = np.array([
            [solution.get_objectives()[idx] for idx in objective_indices]
            for solution in solutions2
        ])

        if np.array_equal(objectives1, objectives2):  # Se idênticos, epsilon 0
            return 0.0

        min_vals = np.min(np.vstack([objectives1, objectives2]), axis=0)  # Mínimos combinados
        max_vals = np.max(np.vstack([objectives1, objectives2]), axis=0)  # Máximos combinados

        ranges = max_vals - min_vals  # Amplitudes
        ranges[ranges == 0] = 1.0  # Evita divisão por zero

        norm_obj1 = np.zeros_like(objectives1, dtype=float)  # Normalizados 1
        norm_obj2 = np.zeros_like(objectives2, dtype=float)  # Normalizados 2

        for i in range(len(objective_indices)):
            if maximize[i]:  # Normalização de max
                norm_obj1[:, i] = (objectives1[:, i] - min_vals[i]) / ranges[i]
                norm_obj2[:, i] = (objectives2[:, i] - min_vals[i]) / ranges[i]
            else:  # Normalização de min (invertida)
                norm_obj1[:, i] = 1.0 - (objectives1[:, i] - min_vals[i]) / ranges[i]
                norm_obj2[:, i] = 1.0 - (objectives2[:, i] - min_vals[i]) / ranges[i]

        epsilon_values = []  # Lista de epsilons individuais

        for sol2 in norm_obj2:  # Para cada solução do conjunto 2
            min_epsilon = float('inf')  # Melhor epsilon contra o conjunto 1

            for sol1 in norm_obj1:  # Compara com cada solução do conjunto 1
                diffs = sol2 - sol1  # Diferença componente a componente
                max_diff = np.max(diffs)  # Máxima diferença (epsilon necessário)
                min_epsilon = min(min_epsilon, max_diff)  # Atualiza mínimo

            epsilon_values.append(min_epsilon)  # Guarda epsilon desta solução

        epsilon = max(epsilon_values) if epsilon_values else 0.0  # Epsilon final = pior caso

        return min(1.0, max(-1.0, epsilon))  # Clampa entre -1 e 1 por segurança numérica

    @staticmethod
    def hypervolume_truncate(solutions: List[Any],
                           max_size: int,
                           objective_indices: List[int] = [0, 1, 2, 3],
                           maximize: List[bool] = [True, True, False, False]) -> List[Any]:
        if len(solutions) <= max_size:  # Se já dentro do limite
            return solutions  # Retorna como está

        truncated = solutions.copy()  # Cópia superficial da lista

        while len(truncated) > max_size:  # Enquanto exceder
            min_contribution = float('inf')  # Menor contribuição de HV encontrada
            min_index = -1  # Índice do candidato a remoção

            for i in range(len(truncated)):  # Para cada solução
                contribution = MultiObjectiveMetrics.calculate_hypervolume_contribution(
                    truncated, i, objective_indices, maximize)  # Contribuição desta solução

                if contribution < min_contribution:  # Atualiza mínimo
                    min_contribution = contribution
                    min_index = i

            if min_index >= 0:  # Remove a menor contribuição
                truncated.pop(min_index)
            else:  # Segurança (fallback aleatório)
                truncated.pop(random.randint(0, len(truncated) - 1))

        return truncated  # Lista truncada pelo critério de hipervolume
