# M4A4 3D

Uma M4A4 (a carabina M4 com trilhos, a mesma arma da M4A4 do CS2), feita por código no Blender, do mesmo jeito
que o `deagle-3d` e o `revolver-3d`. Mede uns 84 cm de comprimento e 26 cm de altura (com o pente) e tem uns 89 mil
triângulos. As proporções foram medidas numa foto de lado de uma M4 de verdade.

As peças ficam separadas:

- **Receptor superior:** topo plano com o trilho Picatinny, a alça de mira destacável atrás com as duas orelhas e a
  abertura, a alavanca de manejo em T embaixo dela, a janela de ejeção à direita com a tampa aberta, o defletor de
  estojo e o assistente do ferrolho.
- **Transportador do ferrolho:** corre por dentro do receptor e aparece pela janela; no tiro ele recua até dentro
  do tubo do amortecedor.
- **Receptor inferior:** o poço do pente, o botão do pente à direita, o seletor e o retém do ferrolho à esquerda,
  os pinos, o gatilho e o guarda-mato fino.
- **Frente:** anel delta e porca do cano, guarda-mão de quatro trilhos com capas nos lados e furos de ventilação,
  massa de mira triangular vazada, cano com o degrau do lança-granadas e o quebra-chamas de gaiola (fechado
  embaixo).
- **Atrás:** cabo de polímero com o ressalto do dedo, tubo do amortecedor com a porca castelo e a coronha retrátil
  vazada com a soleira de borracha.
- **Pente e munição:** o pente de 30 de 5,56, reto em cima e curvo embaixo, com as nervuras dos lados e o cartucho
  de cima deitado no topo, e o estojo que voa no tiro.

O acabamento é alumínio anodizado cinza, aço fosfatizado, polímero cinza-oliva com grão e borracha. Nada de preto puro
(no Minecraft vira borrão), e não tem logo nem escrita de marca.

## Animações

São duas, mais a pose parada:

| Nome | Duração | O que faz |
|---|---|---|
| `tiro` | 4 quadros (0,13 s) | Gatilho, clarão, o transportador recua inteiro, o estojo salta pela janela e some, coice pequeno. O primeiro e o último quadro são a pose parada, então o mod pode repetir a faixa sem parar para fazer a rajada. |
| `recarregar` | 70 quadros (2,3 s) | A arma deita, o botão é apertado, o pente velho cai, o novo sobe e entra com um tranco, e a mão puxa e solta a alavanca em T (o transportador vai junto e volta batendo). |

No `m4a4.blend` elas ficam em sequência na linha do tempo, com marcadores (tiro no quadro 10, recarregar no 20).
No `m4a4.glb` cada uma vira uma animação com nome. O `.obj` sai parado e carregado. O `modelo/animacoes.json` tem
os quadros e os momentos que o mod usa (o disparo, o pente saindo, a troca, o pente entrando e a alavanca).

## Onde estão os arquivos

| Arquivo | Para quê |
|---|---|
| `modelo/m4a4.blend` | Abrir no Blender e mexer. Um objeto por peça. |
| `modelo/m4a4.glb` | Visualizadores de web, Unity, Godot, Windows 3D Viewer. Em metros, com as animações. |
| `modelo/m4a4.obj` (+ `.mtl` e `polimero.png`) | GameMaker e a maioria dos programas 3D. 1 unidade = 1 mm. |
| `modelo/animacoes.json` | Os quadros das animações e dos momentos, para o mod de Minecraft. |
| `render/*.png` | Imagens do modo leve: lado direito, três quartos e um quadro do tiro e um da recarga. |
| `modelo/relatorio.txt` | Medidas e contagem de triângulos de cada peça, e a conferência das animações. |

## Como gerar de novo

Dois cliques no `gerar.bat` (precisa do Blender 5.2 em `C:\Program Files\Blender Foundation`). Faz todas as
imagens em qualidade cheia, leva alguns minutos e ocupa o processador inteiro. Com o PC ocupado, use
`gerar.bat --leve` (quatro imagens pequenas em prioridade mínima). Com `gerar.bat --sem-render`, leva segundos.

## Como mudar uma coisa

Tudo está no `gerar.py`, em milímetros:

- **Quanto o transportador recua no tiro:** troque `CURSO = 60.0` no começo do arquivo.
- **Quanto a alavanca em T é puxada:** troque `CURSO_ALAVANCA = 65.0`.
- **Cor do alumínio:** em `construir()`, procure `material("aluminio_anodizado", (0.17, 0.175, 0.185)` e mude os três
  números (vermelho, verde e azul, de 0 a 1). O aço é a linha `aco_fosfatizado` logo abaixo.
- **Cor do polímero:** na função `textura_polimero()`, a linha `v = 0.34 + 0.08 * t` (o primeiro número é o quão
  claro ele é).

O mod de Minecraft (`revolver-minecraft`) vai usar este modelo. Mudou nome de peça ou quadro de animação aqui,
avise lá antes: o mod depende deles.
