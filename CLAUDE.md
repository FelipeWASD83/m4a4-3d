# CLAUDE.md: m4a4-3d

Modelo 3D de uma M4A4 (a carabina M4 com trilhos, a M4A4 do CS2), gerado por código no Blender, com as animações
de tiro (rajada) e de recarga. Criado em 16/10/2026 a pedido do Felipe, numa das seis sessões em paralelo das armas
novas do mod `revolver-minecraft` (metralhadora, escopeta 12, AK-47, M4A4, M4A1-S e sniper). Esta pasta faz só o
modelo e as animações; a integração no mod (munição 5,56, dano, código Java, exportador) é feita do lado de lá.
Repositório público (escolha dele). O `CLAUDE.md` da raiz vale aqui também, e o `README.md` explica o projeto para
ele.

## Como gerar e conferir

```powershell
& "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" -b --factory-startup --python gerar.py -- --leve
```

O `gerar.bat` faz o mesmo. As opções depois de `--` são as do `deagle-3d`:

- `--sem-render` pula as imagens (uns 20 s);
- `--rapido` faz as imagens em meia resolução;
- `--leve` faz quatro vistas (lado direito, três quartos, um quadro do tiro e um da recarga), com 4 núcleos e
  prioridade mínima;
- `--vistas a,b` escolhe as imagens do modo leve. Os nomes estão no fim de `renderizar`.

**Ele joga no mesmo PC: sem ele pedir render cheio, conferir sempre com `--leve`.**

Conferir no `modelo/relatorio.txt`:

- todas as peças têm que sair `fechada`;
- não pode haver linha `ATENÇÃO`;
- a conferência das animações tem que dizer "nada novo" em todos os momentos. No repouso só o botão do pente
  encosta no receptor inferior (ele entra no corpo de propósito).

## Referência medida

Foto de lado de uma M4 com trilhos do Wikimedia Commons, `PEO M4 Carbine RAS noBG.png` (4050 × 1450, do
PEO Soldier, domínio público). Escala: **4,415 px por mm**, conferida de dois jeitos que batem: o comprimento total
(3700 px = 838 mm, o da M4 com a coronha aberta) e o quebra-chamas (96 px = 21,6 mm). A imagem de inventário da
M4A4 do CS2 (counterstrike.fandom.com, `CS2_M4A4_Inventory.png`) confirmou o desenho: topo plano com trilho e a
alça de mira destacável atrás, guarda-mão de trilhos até a massa de mira triangular, quebra-chamas de gaiola,
coronha retrátil, pente reto curvo embaixo.

Medidas tiradas da foto (X a partir da frente do receptor superior, Z a partir do eixo do cano, em mm):

| Peça | X | Z |
|---|---|---|
| Soleira da coronha | -430 a -420 | 21 a -106 |
| Tubo do amortecedor (visível) | -220 a -206 | raio ~15 |
| Receptor superior | -190 a 0 | -12 a 27, trilho até 34,5 |
| Alavanca em T | -207 a -192 | ~26 |
| Assistente do ferrolho | -118 a -100 | 11 a 31 |
| Janela de ejeção | -91 a -11 | 0 a 19 |
| Cabo (frente e trás no topo, fundo) | -139 / -181, fundo -232 a -170 | -44 a -149 |
| Guarda-mato | -139 a -80 | fundo -80 |
| Botão do pente | -82 | -27 |
| Poço do pente | -76 a 0 | até -66 |
| Pente (fundo) | -49 a 19 | -184 |
| Anel delta e porca | 0 a 26 | raio 28 |
| Guarda-mão de trilhos | 26 a 192 | -28 a 33 |
| Massa de mira | 192 a 249 | -19 a 66 |
| Cano (degrau do lança-granadas) | 249 a 362 | raio 10 / 7,7 / 9,1 |
| Quebra-chamas | 362 a 411 | raio 10,8 |

## Decisões que não se desfazem sem motivo

- **A referência é a M4A4 do CS2, que é uma M4 com trilhos.** As proporções vêm da foto medida acima, não de
  memória (a lição da deagle: a primeira versão "de cabeça" ficou genérica e ele reprovou).
- **Os utilitários de geometria são cópia dos do `deagle-3d`** (`almofada`, `prisma_x`, `tornear`, `varrer`,
  `booleano`, `acabar` com normais por área, `_juntar` recebendo o material, `Faixa`...). Os projetos são
  independentes. Acrescentados aqui: `plano_t` (contorno visto de cima, para a alavanca em T) e `trilho`
  (Picatinny com ranhuras a cada 10 mm).
- **Eixos e unidade:** 1 unidade = 1 mm, boca em +X, o lado direito de quem atira (janela de ejeção, assistente,
  botão do pente) em -Y, Z para cima, eixo do cano em Z = 0, X = 0 na frente do receptor superior.
- **Cores (valores lineares):** alumínio anodizado cinza (0,17, metálico 0,3), aço fosfatizado (0,21, metálico
  0,55), polímero cinza-oliva com textura de grão (`polimero.png`, gravado em sRGB 0,34 a 0,42, que dá 0,10 a 0,15
  linear), soleira de borracha (0,12), pente de alumínio (0,19). Nada de preto puro: no Minecraft preto vira borrão.
  **Sem logo nem escrita de marca.**
  - Metálico alto fazia o estúdio claro se refletir e a arma sair quase branca; e a textura gravada com valores
    lineares (0,13) virava quase preto, porque o PNG é lido como sRGB.
  - O render usa exposição -1,6: o estúdio do `deagle-3d`, ampliado para 84 cm, estourava a M4 em branco. Isso só
    muda as imagens, não as cores do modelo.
- **Tampa da janela aberta em repouso**, pendurada para baixo, como numa arma que já atirou: deixa ver o
  transportador indo e voltando na rajada. É a peça `tampa_janela`, parada, com a origem na dobradiça (girar 180° em
  X fecha). Ela não está em `pecas` porque nenhuma faixa mexe nela.
- **O transportador (`ferrolho`) corre por dentro**: o receptor superior tem uma cavidade de raio 13, o inferior e a
  coronha têm um canal, e o tubo do amortecedor e a porca castelo são ocos. No tiro ele recua 60 mm (até dentro do
  tubo). A alavanca em T não anda no tiro (como na arma real), só na recarga, e puxa o transportador junto.
- **Pente reto até sair do poço e só então curvo** para a frente. O poço é reto: na recarga o pente velho cai reto
  até sair inteiro (quadro 19) e só depois tomba; o novo chega inclinado, se alinha antes de chegar à boca do poço e
  entra reto. Com a curva começando antes, a frente do pente atravessava o poço.
- **O cartucho de cima é filho do pente** e usa a mesma malha do `estojo_ejetado` (o mod desenha os dois com o
  mesmo modelo). Fica deitado a 4 mm para a esquerda (a fila dupla), logo abaixo do transportador.
- **O tiro tem 4 quadros**, o primeiro e o último em repouso, para o mod repetir a faixa na rajada sem pulo:
  quadro 2 é o disparo (clarão, transportador todo atrás, estojo na janela, coice), quadro 3 o transportador
  voltando, o clarão menor e o estojo longe, quadro 4 tudo em repouso de novo.

## Contrato com o mod

O exportador da sessão principal (no `revolver-minecraft`) lê o `modelo/m4a4.blend` e o `modelo/animacoes.json`.
Ele depende de:

- o empty raiz `m4a4`, no cabo (`RECUO = (-172, 0, -88)`), com tudo filho dele;
- os nomes das peças que mexem: `ferrolho`, `alavanca`, `gatilho`, `pente` (origem no centro do fundo, filhos
  `estojo_topo` e `bala_topo`), `botao_pente`, `clarao` (escala 0 em repouso, origem na boca) e `estojo_ejetado`
  (escala 0 em repouso, mesma malha do `estojo_topo`);
- as faixas de NLA `repouso` (HOLD), `tiro` e `recarregar`, com os quadros e eventos do `animacoes.json`:

| Faixa | Início na cena | Quadros | Eventos (1 = primeiro quadro da faixa) |
|---|---|---|---|
| `repouso` | 1 | 2 | nenhum |
| `tiro` | 10 | 4 | disparo 2 |
| `recarregar` | 20 | 70 | pente_sai 14, troca 27, pente_entra 44, alavanca 55 |

Renomear peça ou mudar quadro aqui quebra o mod. Mudou, regenerar e avisar quem cuida do exportador de lá.

## O que não tem (de propósito, não foi pedido)

Sem animação de tiro seco, sem faixa com o ferrolho travado aberto (a M4 trava aberta no último tiro, mas o
contrato pediu só `tiro` e `recarregar`), sem vídeo, sem LOD e sem render cheio no commit (só os do `--leve`).
