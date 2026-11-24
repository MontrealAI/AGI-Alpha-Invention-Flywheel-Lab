"""Reuse the qualified HARNESS route and checkpoint reservations for research stages."""

from types import SimpleNamespace
from time import time
from uuid import uuid4

from bridge.output_schema import prepare_schema, validate_output
from inventor import Model
from provider import request_plan
from research import ResearchRun
from pages import digest
from study import lock


class Constructor(Model):
    def __init__(self, config, model, schema):
        super().__init__(SimpleNamespace(config=config,model=model,provider='localhost-inference'))
        self.schema=schema

    def call(self,prompt,limit):
        if not self.provider.models[self.name].json_schema:
            return super().call(prompt,limit)
        plan=request_plan(self.runtime,self.provider,self.name,prompt,limit,False)
        plan['schema_sha256']=digest(self.schema)
        plan['approval_sha256']=digest(plan)
        request={'provider':self.provider.id,'model':self.name,'prompt':prompt,
                 'max_output_tokens':limit,'run_id':uuid4().hex,'json_schema':self.schema}
        return self.runtime.generate(request,expected_provider=self.provider),plan


def step(workspace,config,model,schema,prompt,kind,request_tokens,attempts=2,*,validate=lambda value:value,
         deadline=None,expected_config=None):
    workspace.mkdir(mode=0o700,parents=True,exist_ok=True)
    schema=prepare_schema(schema)
    constructor=Constructor(config,model,schema)
    if expected_config is not None and constructor.config_sha256!=expected_config:
        raise ValueError('CONFIG_DRIFT')
    with lock(workspace):
        run=ResearchRun(workspace/'run.json',constructor,request_tokens*attempts,{
            'kind':kind,'request_tokens':request_tokens,'prompt_sha256':digest(prompt),
            'schema_sha256':digest(schema),'attempts':attempts})
        if run.state['status']!='RUNNING':
            if run.state['status']=='SEALED':
                validate_output(run.state['result'],schema)
            return run.state
        for settled in run.state['events']:
            if settled['status']=='SEALED':
                validate_output(settled['candidate'],schema)
                return run.finish('SEALED',settled['candidate'])
        while run.remaining>=min(96,request_tokens) and len(run.state['events'])<attempts:
            if deadline is not None and int(time())>=deadline:
                raise ValueError('LEASE_EXPIRED')
            answer,event=run.invoke(prompt,{})
            if answer is not None:
                event['draft']=answer
            try:
                validate_output(answer,schema)
                candidate=validate(answer)
                event.update(status='SEALED',candidate=candidate)
                run.settle(event)
                return run.finish('SEALED',candidate)
            except (ValueError,TypeError,KeyError) as error:
                event.update(status='REFUSED',diagnosis=str(error)[:240])
                run.settle(event)
        return run.finish('ABSTAIN')


def object_schema(properties):
    return {'type':'object','properties':properties,'required':list(properties),'additionalProperties':False}


def brief(length):
    return {'type':'string','minLength':1,'maxLength':length}
