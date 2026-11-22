// GOAL GENESIS Ω — bounded record challenge, not proof of a new graph.
// Baseline: exact published Alegre-Fiol-Yebra 70-vertex cubic diameter-5 graph.
// Candidate families: all disjoint two-edge insertions; randomized three-edge
// insertions; degree-preserving double-edge swaps with simulated annealing.
// The independent proof checker is verify.py; never trust this searcher's score.
#include <array>
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <random>
#include <set>
#include <string>
#include <utility>
#include <vector>
#include <chrono>

using namespace std;
constexpr int N=72;
using Edge=pair<int,int>;
struct Graph {
  array<array<unsigned char,N>,N> A{};
  void put(int u,int v){A[u][v]=A[v][u]=1;}
  void del(int u,int v){A[u][v]=A[v][u]=0;}
  bool has(int u,int v)const{return A[u][v]!=0;}
  vector<Edge> edges(int n) const {
    vector<Edge> e;
    for(int i=0;i<n;i++)for(int j=i+1;j<n;j++)if(has(i,j))e.push_back({i,j});
    return e;
  }
  bool degree_three()const{
    for(int i=0;i<N;i++){
      int d=0;for(int j=0;j<N;j++)d+=has(i,j);
      if(d!=3||has(i,i))return false;
    }
    return true;
  }
};
int deficit(const Graph &g) {
  // Exact unordered pair count of graph distances exceeding five.
  // Use compact adjacency, independently verified by verify.py.
  int nb[N][3],deg[N]{};
  for(int i=0;i<N;i++)for(int j=0;j<N;j++)if(g.has(i,j)){
    if(deg[i]>=3)return N*N;
    nb[i][deg[i]++]=j;
  }
  int missing=0;
  for(int src=0;src<N;src++){
    bool seen[N]{};
    int q[N],head=0,tail=1;q[0]=src;seen[src]=true;
    for(int depth=0;depth<5;depth++){
      int stop=tail;
      while(head<stop){
        int u=q[head++];
        for(int k=0;k<deg[u];k++){
          int v=nb[u][k];
          if(!seen[v]){seen[v]=true;q[tail++]=v;}
        }
      }
    }
    missing+=N-tail;
  }
  return missing/2;
}

Graph read_base(const string&path) {
  Graph g;ifstream f(path);
  if(!f)throw runtime_error("cannot read published incumbent");
  string line;int v=0;
  while(getline(f,line)){
    if(line.empty()||line[0]=='#')continue;
    istringstream is(line);int k;
    if(!(is>>k)||k!=v++)throw runtime_error("incumbent node sequence invalid");
    int w;while(is>>w){if(w<=k||w>=70)throw runtime_error("invalid incumbent forward edge");g.put(k,w);}
  }
  if(v!=70)throw runtime_error("incumbent must have 70 vertices");
  for(int u=0;u<70;u++){
    int degree=0;for(int j=0;j<70;j++)degree+=g.has(u,j);
    if(degree!=3)throw runtime_error("incumbent must be cubic");
  }
  return g;
}
Graph insert(const Graph&base,vector<Edge> selected,int flips, int kind){
  Graph g=base;
  for(size_t k=0;k<selected.size();k++){
    auto [a,b]=selected[k];g.del(a,b);
    if((flips>>k)&1)swap(a,b);
    g.put(70,a);g.put(71,b);
  }
  if(kind==2)g.put(70,71);
  return g;
}
void write_graph(const Graph&g,const string&name){
  ofstream f(name);f<<"{\n  \"schema\": \"montreal-ai/degree-diameter-candidate/v1\",\n";
  f<<"  \"claim\": \"research_candidate_not_record\",\n";
  f<<"  \"adjacency\": [\n";
  for(int i=0;i<N;i++){
    f<<"    [";bool first=true;
    for(int j=0;j<N;j++)if(g.has(i,j)){if(!first)f<<", ";f<<j;first=false;}
    f<<"]"<<(i<N-1?",":"")<<"\n";
  }
  f<<"  ]\n}\n";
}
int main(int argc,char**argv){
  if(argc!=6 && argc!=7){cerr<<"usage: search INPUT_BASE BEST_JSON ATTEMPTS RESTARTS SEED [--exhaustive]\n";return 2;}
  string source=argv[1],dest=argv[2];
  int attempts=stoi(argv[3]),restarts=stoi(argv[4]);unsigned long long seed=stoull(argv[5]);
  if(attempts<=0||restarts<=0)throw runtime_error("positive attempts/restarts required");
  mt19937_64 rng(seed);auto start=chrono::steady_clock::now();
  auto base=read_base(source);auto E=base.edges(70);
  if(E.size()!=105)throw runtime_error("incumbent edges !=105");
  Graph best;int best_score=INT32_MAX;
  long long all_two=0,three=0,swaps=0,accepted=0,triangle=0;
  int min_two=INT32_MAX,min_three=INT32_MAX,min_triangle=INT32_MAX;
  auto update=[&](const Graph&candidate,int score){if(score<best_score){best_score=score;best=candidate;write_graph(best,dest);cerr<<"NEW_BEST "<<best_score<<" attempted="<<(all_two+three+triangle+swaps)<<"\n";}};
  // All distinct 2-edge insertions, both essential pairings. Strong local
  // comparator: construction inherited directly from the incumbent.
  for(int i=0;i<(int)E.size();i++)for(int j=i+1;j<(int)E.size();j++){
    auto [a,b]=E[i];auto[c,d]=E[j];
    if(a==c||a==d||b==c||b==d)continue;
    for(int flip=0;flip<2;flip++){
      auto cand=insert(base,{E[i],E[j]},flip,2);
      if(!cand.degree_three())throw runtime_error("invalid two-edge insertion");
      all_two++;int sc=deficit(cand);min_two=min(min_two,sc);update(cand,sc);
      if(best_score==0)goto final;
    }
  }
  // Vertex-to-triangle expansion (Y-to-Delta), another complete local
  // two-vertex augmentation family: one of the 3 original neighbors stays
  // attached to the retained old vertex, the remaining two to new nodes.
  for(int v=0;v<70;v++){
    vector<int> neighbors;
    for(int u=0;u<70;u++)if(base.has(v,u))neighbors.push_back(u);
    if(neighbors.size()!=3)throw runtime_error("incumbent vertex not cubic");
    for(int k=0;k<3;k++){
      Graph cand=base;
      for(int u:neighbors)cand.del(v,u);
      cand.put(v,70);cand.put(v,71);cand.put(70,71);
      cand.put(v,neighbors[k]);
      cand.put(70,neighbors[(k+1)%3]);cand.put(71,neighbors[(k+2)%3]);
      if(!cand.degree_three())throw runtime_error("invalid triangle expansion");
      triangle++;
      int sc=deficit(cand);min_triangle=min(min_triangle,sc);update(cand,sc);
      if(best_score==0)goto final;
    }
  }
  // Every disjoint three-edge insertion yields four distinct endpoint
  // assignments, up to the exchange of the two new vertices.
  // Exhaustive mode certificates apply only to THIS restricted family.
  if(argc==7 && string(argv[6])=="--exhaustive"){
    for(int i=0;i<(int)E.size();i++)for(int j=i+1;j<(int)E.size();j++)
      for(int k=j+1;k<(int)E.size();k++){
        auto [a,b]=E[i];auto[c,d]=E[j];auto[e,f]=E[k];
        set<int> endpoints={a,b,c,d,e,f};if(endpoints.size()!=6)continue;
        for(int flips=0;flips<4;flips++){
          auto cand=insert(base,{E[i],E[j],E[k]},flips,3);
          three++;int sc=deficit(cand);min_three=min(min_three,sc);update(cand,sc);
          if(best_score==0)goto final;
        }
      }
  } else {
    for(int t=0;t<attempts;t++){
      array<int,3> pick;set<int> index;
      while(index.size()<3)index.insert(int(rng()%E.size()));
      int z=0;for(int k:index)pick[z++]=k;
      auto [a,b]=E[pick[0]];auto[c,d]=E[pick[1]];auto[e,f]=E[pick[2]];
      set<int> endpoints={a,b,c,d,e,f};if(endpoints.size()!=6)continue;
      int flips=int(rng()%4);
      auto cand=insert(base,{E[pick[0]],E[pick[1]],E[pick[2]]},flips,3);
      three++;int sc=deficit(cand);min_three=min(min_three,sc);update(cand,sc);
      if(best_score==0)goto final;
    }
  }
  // Unrestricted degree-preserving 2-switch local moves after incumbent-derived
  // initialization. Anneal: accepting uphill moves is a genuine search option.
  for(int epoch=0;epoch<restarts;epoch++){
    Graph current=best;int cost=best_score;
    double t0=3.0+(epoch%3)*2.0,t1=0.04;
    int per=attempts/max(restarts,1);if(per<1000)per=1000;
    for(int it=0;it<per;it++){
      auto edges=current.edges(N);
      int ia=int(rng()%edges.size()),ib=int(rng()%edges.size());
      if(ia==ib)continue;
      auto [a,b]=edges[ia];auto[c,d]=edges[ib];
      if(a==c||a==d||b==c||b==d)continue;
      if(rng()&1)swap(c,d);
      if(a==c||b==d||current.has(a,c)||current.has(b,d))continue;
      Graph next=current;next.del(a,b);next.del(c,d);next.put(a,c);next.put(b,d);
      swaps++;int score=deficit(next);
      update(next,score);
      if(best_score==0)goto final;
      double fraction=double(it)/per;
      double temp=t0*pow(t1/t0,fraction);
      if(score<=cost||generate_canonical<double,53>(rng)<exp(double(cost-score)/temp)){
        current=move(next);cost=score;accepted++;
      }
    }
  }
final:
  if(!best.degree_three())throw runtime_error("best candidate violates cubic graph property");
  auto end=chrono::steady_clock::now();
  cout<<"{\"incumbent_order\":70,\"target_order\":72,\"best_pairs_beyond_5\":"<<best_score;
  cout<<",\"found_record\":"<<(best_score==0?"true":"false");
  cout<<",\"insertions_two\":"<<all_two<<",\"insertions_three\":"<<three;
  cout<<",\"vertex_triangle_expansions\":"<<triangle;
  cout<<",\"min_two_edge_deficit\":"<<min_two<<",\"min_three_edge_deficit\":"<<min_three<<",\"min_triangle_deficit\":"<<min_triangle;
  cout<<",\"proposed_degree_preserving_swaps\":"<<swaps<<",\"accepted_swaps\":"<<accepted;
  cout<<",\"attempts_setting\":"<<attempts<<",\"restarts\":"<<restarts<<",\"seed\":"<<seed;
  cout<<",\"exhaustive_3edge\":"<<(argc==7?"true":"false");
  cout<<",\"wall_seconds\":"<<chrono::duration<double>(end-start).count();
  cout<<",\"candidate_path\":\""<<dest<<"\"}\n";
}
