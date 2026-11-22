// Independent fixed-budget 2-sheet voltage-lift exploration, research only.
// Protocol: research/omega_voltage_lift_072/PROTOCOL.md, frozen at 9cfb11756ee05f4b9731e668355e44dff3410c53.
#include <array>
#include <algorithm>
#include <cstdint>
#include <cmath>
#include <cstdlib>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <numeric>
#include <random>
#include <stdexcept>
#include <string>
#include <vector>
using namespace std;
constexpr int BASE=36, SHEETS=2, N=72, M=54, STEPS=25000, RUNS=8;
struct E {int u,v; unsigned s;};
using Edges=array<E,M>;
struct Measure {int violations=0; int diameter=0; bool connected=true;};
struct Counts {uint64_t seed=0, draws=0; int start=0,best=0,best_step=-1,valid=0,invalid=0,accepted=0,worsening=0;};
static bool compatible(const Edges& es){
  array<int,BASE> degree{};
  bool present[BASE][BASE]{};
  for (const auto& e: es){
    if(e.u<0||e.u>=BASE||e.v<0||e.v>=BASE||e.u==e.v||e.s>1||present[e.u][e.v])return false;
    present[e.u][e.v]=present[e.v][e.u]=true;
    degree[e.u]++;degree[e.v]++;
  }
  for (int d:degree)if(d!=3)return false;
  return true;
}
static Edges make_base(mt19937_64 &rng,uint64_t &draws){
  array<int,BASE*3> stubs;
  for(int i=0;i<BASE*3;i++)stubs[i]=i/3;
  for(;;){
    draws++;
    shuffle(stubs.begin(),stubs.end(),rng);
    Edges es{};
    for(int j=0;j<M;j++){
      int a=stubs[2*j],b=stubs[2*j+1];
      es[j]={min(a,b),max(a,b),(unsigned)(rng()&1)};
    }
    if(compatible(es))return es;
  }
}
static bool switched(Edges& es, mt19937_64 &rng){
  int i=(int)(rng()%M),j=(int)(rng()%(M-1));
  if(j>=i)j++;
  auto a=es[i], b=es[j];
  if(a.u==b.u||a.u==b.v||a.v==b.u||a.v==b.v)return false;
  E c,d;
  if(rng()&1){c={min(a.u,b.u),max(a.u,b.u),a.s};d={min(a.v,b.v),max(a.v,b.v),b.s};}
  else {c={min(a.u,b.v),max(a.u,b.v),a.s};d={min(a.v,b.u),max(a.v,b.u),b.s};}
  if(c.u==c.v||d.u==d.v|| (c.u==d.u&&c.v==d.v))return false;
  for(int k=0;k<M;k++)if(k!=i&&k!=j){
    if((es[k].u==c.u&&es[k].v==c.v)||(es[k].u==d.u&&es[k].v==d.v))return false;
  }
  es[i]=c;es[j]=d;
  return true;
}
static Measure measure(const Edges& es){
  int adj[N][3]{};
  int deg[N]{};
  for(const auto&e:es)for(int p=0;p<2;p++){
    int u=2*e.u+p, v=2*e.v+(p^e.s);
    if(u==v||deg[u]>=3||deg[v]>=3)throw runtime_error("INVALID_LIFT");
    adj[u][deg[u]++]=v; adj[v][deg[v]++]=u;
  }
  for(int i=0;i<N;i++)if(deg[i]!=3)throw runtime_error("NON_CUBIC_LIFT");
  Measure m;
  for(int root=0;root<N;root++){
    int dist[N];fill(begin(dist),end(dist),-1);
    int q[N];int front=0,back=0;
    q[back++]=root;dist[root]=0;
    while(front<back){
      int u=q[front++];
      if(dist[u]==5)continue;
      for(int k=0;k<3;k++){
        int v=adj[u][k];
        if(dist[v]==-1){dist[v]=dist[u]+1;q[back++]=v;}
      }
    }
    for(int k=root+1;k<N;k++)if(dist[k]<0)m.violations++;
  }
  m.connected=(m.violations< N*(N-1)/2);
  return m;
}
static void write_json(const string &path,const Edges& best,int score,int best_seed,int best_step,const array<Counts,RUNS>& logs){
  ofstream out(path);
  if(!out)throw runtime_error("CANNOT_WRITE_OUTPUT");
  out<<"{\n  \"schema\": \"agi-alpha/omega-voltage-lift-072/v1\",\n";
  out<<"  \"experiment\": \"frozen-eight-seed-2-lift\",\n  \"protocol_commit\": \"9cfb11756ee05f4b9731e668355e44dff3410c53\",\n";
  out<<"  \"n\": 72, \"base_n\": 36, \"base_edges\": 54, \"steps_per_seed\": 25000, \"seeds\": 8, \"total_proposals\": 200000,\n";
  out<<"  \"best_violations\": "<<score<<", \"best_seed\": "<<best_seed<<", \"best_step\": "<<best_step<<",\n";
  out<<"  \"edges\": [\n";
  for(int e=0;e<M;e++)for(int p=0;p<2;p++){
    int u=2*best[e].u+p, v=2*best[e].v+(p^best[e].s);
    if(u>v)swap(u,v);
    out<<"    ["<<u<<", "<<v<<"]"<<((e==M-1&&p==1)?"\n":",\n");
  }
  out<<"  ],\n  \"per_seed\": [\n";
  for(int k=0;k<RUNS;k++){
    const auto&r=logs[k];
    out<<"    {\"seed\": "<<r.seed<<", \"base_generation_draws\": "<<r.draws<<", \"initial_violations\": "<<r.start<<", \"best_violations\": "<<r.best<<", \"best_step\": "<<r.best_step<<", \"valid_proposals\": "<<r.valid<<", \"invalid_proposals\": "<<r.invalid<<", \"accepted_proposals\": "<<r.accepted<<", \"accepted_worsening\": "<<r.worsening<<"}";
    out<<(k==RUNS-1?"\n":",\n");
  }
  out<<"  ]\n}\n";
}
int main(int argc,char**argv){
  try{
    if(argc!=2)throw runtime_error("usage: search /absolute/output.json");
    array<Counts,RUNS> logs{};
    int best_score= N*(N-1)/2+1,best_seed=-1,best_step=-1;
    Edges best_edges{};
    for(int k=0;k<RUNS;k++){
      uint64_t seed=2026111601ULL+k;
      mt19937_64 rng(seed);
      Counts stats;stats.seed=seed;
      Edges current=make_base(rng,stats.draws);
      int current_score=measure(current).violations;
      stats.start=stats.best=current_score;
      if(current_score<best_score){best_score=current_score;best_edges=current;best_seed=(int)seed;best_step=-1;}
      for(int step=0;step<STEPS;step++){
        Edges candidate=current;
        if((rng()&1)==0){int t=(int)(rng()%M);candidate[t].s^=1u;}
        else if(!switched(candidate,rng)){stats.invalid++;continue;}
        stats.valid++;
        int cand=measure(candidate).violations;
        double temp=60.0*(1.0-(double)step/STEPS)+0.25;
        const bool accept=(cand<=current_score) || generate_canonical<double,64>(rng)<exp(-(double)(cand-current_score)/temp);
        if(accept){
          if(cand>current_score)stats.worsening++;
          stats.accepted++;current=candidate;current_score=cand;
        }
        // The global witness is retained from every inspected proposal, including
        // a proposed graph that did not survive the subsequent annealing decision.
        if(cand<stats.best){stats.best=cand;stats.best_step=step;}
        if(cand<best_score){best_score=cand;best_edges=candidate;best_seed=(int)seed;best_step=step;}
      }
      logs[k]=stats;
      cerr<<"seed "<<seed<<" initial="<<stats.start<<" best="<<stats.best<<" valid="<<stats.valid<<" invalid="<<stats.invalid<<"\n";
    }
    write_json(argv[1],best_edges,best_score,best_seed,best_step,logs);
    cout<<"completed 200000 registered proposals; minimum violating pairs="<<best_score<<"\n";
    return 0;
  }catch(const exception&ex){cerr<<ex.what()<<"\n";return 1;}
}
